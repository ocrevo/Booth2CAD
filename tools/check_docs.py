"""Check the repository's documents: links, alt text, private traces and facts that must agree everywhere.

Run from anywhere: ``python tools/check_docs.py``. Exits 1 and lists every problem when a check fails. Standard library only, so CI
can run it before anything is installed.

Checks:
- every relative link and image in a tracked Markdown file (and llms.txt) points to a file that exists, and so does every link
  into this repository on GitHub (``REPO_URL`` + ``blob/main/`` or ``tree/main/``), which llms.txt uses;
- SKILL.md links stay inside the skill folder, because the skill is installed on its own;
- every image has alt text;
- no tracked text file holds a client name, a personal path or something that looks like an API key;
- name, version, license and requirements agree across README.md, README.zh-CN.md, SKILL.md, the skill READMEs,
  web/package.json, CITATION.cff and llms.txt;
- the canonical definition sentence is the same in README.md, llms.txt and docs/github-settings.md;
- both front pages have a FAQ.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = 'booth-image-to-model'
NAME = 'booth-image-to-model'
LICENSE = 'Apache-2.0'
REPO_URL = 'https://github.com/ocrevo/booth-image-to-model/'
REPO_LINK = re.compile(re.escape(REPO_URL) + r'(?:blob|tree)/main/(.*)$')

# Client names, personal paths and key-like strings. The pattern is split so this file does not match itself.
TRACES = re.compile('|'.join([
    'cl' + 'eer', r'\bwx' + '_', r'\b[D-Z]:[\\/]',r'C:[\\/]Users', '/mnt/' + 'data', 'Jing' + 'xuan',
    r'\bsk-[A-Za-z0-9]{20}',
]), re.I)
TEXT_SUFFIXES = {'.md', '.txt', '.py', '.js', '.mjs', '.json', '.html', '.css', '.yml', '.yaml', '.cff', '.toml', '.cfg', '.ini', ''}
LINK = re.compile(r'(!?)\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
HTML_IMG = re.compile(r'<img\b[^>]*>', re.I)


def tracked():
    """Files git tracks plus new files it does not ignore, minus files deleted in the working copy."""
    out = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT,
                         capture_output=True, check=True).stdout.decode('utf-8')
    return sorted({p for p in out.split('\0') if p and (ROOT / p).is_file()})


def without_code(text):
    """Markdown text with fenced blocks and inline code blanked, keeping line numbers."""
    lines, fenced = [], False
    for line in text.split('\n'):
        if line.lstrip().startswith(('```', '~~~')):
            fenced = not fenced
            lines.append('')
            continue
        lines.append('' if fenced else re.sub(r'`[^`]*`', '', line))
    return lines


def check_links(files, problems):
    for rel in files:
        if not (rel.endswith('.md') or rel == 'llms.txt'):
            continue
        path = ROOT / rel
        for number, line in enumerate(without_code(path.read_text(encoding='utf-8')), 1):
            for bang, alt, target in LINK.findall(line):
                where = f'{rel}:{number}'
                if bang and not alt.strip():
                    problems.append(f'{where}: image without alt text ({target})')
                repo = REPO_LINK.match(target)
                if not repo and (re.match(r'^[a-z][a-z0-9+.-]*:', target, re.I) or target.startswith('#')):
                    continue
                file_part = (repo.group(1) if repo else target).split('#', 1)[0].split('?', 1)[0]
                if not file_part:
                    continue
                resolved = ((ROOT if repo else path.parent) / file_part).resolve()
                if not resolved.exists():
                    problems.append(f'{where}: broken link {target}')
                elif rel == f'{SKILL}/SKILL.md' and not resolved.is_relative_to((ROOT / SKILL).resolve()):
                    problems.append(f'{where}: SKILL.md links outside the skill folder ({target})')
            for tag in HTML_IMG.findall(line):
                if not re.search(r'\balt\s*=\s*"[^"]+"', tag):
                    problems.append(f'{rel}:{number}: <img> without alt text')


def check_traces(files, problems):
    for rel in files:
        path = ROOT / rel
        if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 5_000_000:
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.split('\n'), 1):
            match = TRACES.search(line)
            if match:
                problems.append(f'{rel}:{number}: private trace {match.group(0)!r}')


def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


def squash(text):
    return re.sub(r'\s+', ' ', text.replace('**', '')).strip()


def check_facts(problems):
    skill_md = read(f'{SKILL}/SKILL.md')
    front = skill_md.split('---', 2)[1]
    version = re.search(r'^  version:\s*"?([^"\s]+)"?\s*$', front, re.M)
    if not version:
        problems.append('SKILL.md: no metadata version')
        return
    version = version.group(1)
    package = json.loads(read('web/package.json'))
    citation = read('CITATION.cff')

    def expect(where, ok, what):
        if not ok:
            problems.append(f'{where}: {what}')

    expect('SKILL.md', re.search(rf'^name:\s*{NAME}\s*$', front, re.M), f'name is not {NAME}')
    expect('SKILL.md', re.search(rf'^license:\s*{LICENSE}\b', front, re.M), f'license is not {LICENSE}')
    expect('web/package.json', package.get('version') == version, f'version {package.get("version")} is not {version}')
    expect('web/package.json', package.get('license') == LICENSE, f'license is not {LICENSE}')
    expect('web/package.json', package.get('engines', {}).get('node') == '>=22.15', 'engines.node is not >=22.15')
    expect('CITATION.cff', re.search(rf'^version:\s*"?{re.escape(version)}"?\s*$', citation, re.M), f'version is not {version}')
    expect('CITATION.cff', re.search(rf'^license:\s*{LICENSE}\s*$', citation, re.M), f'license is not {LICENSE}')
    for key in ('cff-version', 'message', 'title', 'authors'):
        expect('CITATION.cff', re.search(rf'^{key}:', citation, re.M), f'required key {key} missing')
    expect('README.md', f'Version {version}' in read('README.md'), f'does not say "Version {version}"')
    expect('README.zh-CN.md', f'当前版本 {version}' in read('README.zh-CN.md'), f'does not say "当前版本 {version}"')
    for rel in (f'{SKILL}/README.md', f'{SKILL}/README_CN.md'):
        expect(rel, f'v{version}' in read(rel).split('\n', 4)[2], f'title line does not carry v{version}')
    expect('CHANGELOG.md', f'# {version} ' in read(f'{SKILL}/CHANGELOG.md'), f'no entry for {version}')

    # Requirements: the same minimum versions in every place that states them.
    for rel in ('README.md', 'README.zh-CN.md', f'{SKILL}/SKILL.md', f'{SKILL}/README.md', f'{SKILL}/README_CN.md', 'llms.txt'):
        text = read(rel)
        expect(rel, 'Python 3.10+' in text, 'does not state Python 3.10+')
        expect(rel, re.search(r'Blender 4\.0(\+| or newer)', text), 'does not state Blender 4.0+')
        expect(rel, LICENSE in text, f'does not name the {LICENSE} license')
    for rel in ('README.md', 'README.zh-CN.md'):
        expect(rel, '22.15+' in read(rel), 'does not state Node.js 22.15+')

    # The canonical definition: the first bold paragraph of README.md, the llms.txt summary, the GitHub description.
    readme = read('README.md')
    bold = re.search(r'^\*\*(booth-image-to-model .+?)\*\*', readme, re.M | re.S)
    summary = re.search(r'^> (.+)$', read('llms.txt'), re.M)
    settings = re.search(r'^> (.+)$', read('docs/github-settings.md'), re.M)
    if not (bold and summary and settings):
        problems.append('canonical definition not found in README.md, llms.txt or docs/github-settings.md')
    else:
        sentence = squash(bold.group(1))
        expect('llms.txt', squash(summary.group(1)) == sentence, 'summary differs from the README definition')
        expect('docs/github-settings.md', squash(settings.group(1)).startswith(sentence),
               'description does not start with the README definition')
        expect('docs/github-settings.md', len(squash(settings.group(1))) <= 350, 'description is longer than 350 characters')
    expect('llms.txt', read('llms.txt').startswith(f'# {NAME}\n'), f'does not start with "# {NAME}"')
    expect('README.md', re.search(r'^## FAQ$', readme, re.M), 'no FAQ section')
    expect('README.zh-CN.md', re.search(r'^## 常见问题$', read('README.zh-CN.md'), re.M), 'no FAQ section (常见问题)')


def main():
    files = tracked()
    problems = []
    check_links(files, problems)
    check_traces(files, problems)
    check_facts(problems)
    for problem in problems:
        print(problem)
    print(f'check_docs: {len(files)} files, {len(problems)} problem(s)')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
