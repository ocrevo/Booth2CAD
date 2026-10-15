"""Start the studio: the flow page, the editor and the local API on http://127.0.0.1:8800/

    python web/server/run.py                       # opens the browser
    python web/server/run.py --port 8801 --no-browser --jobs-dir D:/somewhere

Large-model reading (optional, only for the automatic reading step): set OPENAI_API_KEY (the key of whichever OpenAI-compatible
service you use; or paste it on the page, where it is kept in memory only). Pick the service with --provider openai (default) or
--provider deepseek, which presets base URL, model and request style; --openai-base-url / --openai-model / --openai-style
(responses | chat | chat-json) or the environment variables OPENAI_BASE_URL, OPENAI_MODEL, OPENAI_API_STYLE override the preset.
OPENAI_REASONING_EFFORT (reasoning models only) and OPENAI_MAX_OUTPUT_TOKENS (default 32000; lower it for a model or service
whose output limit is smaller) tune the request. Without a key every other step works.
Jobs are written to output/studio/<job>/ (git-ignored). Blender is found through BLENDER_EXE, PATH or the default install path.
"""
from __future__ import annotations
import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402
from server import Config, create_server  # noqa: E402

DEFAULT_JOBS = HERE.parents[1] / 'output' / 'studio'
STYLES = ('responses', 'chat', 'chat-json')
PRESETS = {      # what to talk to; any model name your account has can be set instead
    'openai': {'base_url': 'https://api.openai.com/v1', 'model': 'gpt-5.5', 'style': 'responses'},
    'deepseek': {'base_url': 'https://api.deepseek.com', 'model': 'deepseek-flash', 'style': 'chat-json'},
}


def llm_settings(args, env):
    """base URL, model and request style: an explicit flag, else the environment, else the provider's preset."""
    preset = PRESETS[args.provider]
    return {'base_url': args.openai_base_url or env.get('OPENAI_BASE_URL') or preset['base_url'],
            'model': args.openai_model or env.get('OPENAI_MODEL') or preset['model'],
            'style': args.openai_style or env.get('OPENAI_API_STYLE') or preset['style']}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--port', type=int, default=8800)
    p.add_argument('--jobs-dir', default=str(DEFAULT_JOBS))
    p.add_argument('--no-browser', action='store_true')
    p.add_argument('--verbose', action='store_true')
    p.add_argument('--provider', choices=sorted(PRESETS), default=os.environ.get('LLM_PROVIDER') or 'openai', help='preset for base URL, model and request style')
    p.add_argument('--openai-base-url', default=None)
    p.add_argument('--openai-model', default=None)
    p.add_argument('--openai-style', choices=STYLES, default=None,
                   help='responses = OpenAI Responses API; chat = Chat Completions with a strict schema; chat-json = Chat Completions with JSON mode only')
    p.add_argument('--openai-effort', default=os.environ.get('OPENAI_REASONING_EFFORT') or None, help='reasoning effort for reasoning models (omit for others)')
    p.add_argument('--openai-max-output-tokens', type=int, default=int(os.environ.get('OPENAI_MAX_OUTPUT_TOKENS') or 32000),
                   help='output token limit sent with each reading request (lower it when the model or service refuses 32000)')
    a = p.parse_args(argv)
    llm = llm_settings(a, os.environ)
    if llm['style'] not in STYLES:
        print(f"OPENAI_API_STYLE must be one of {', '.join(STYLES)}", file=sys.stderr)
        return 2
    key = os.environ.pop('OPENAI_API_KEY', None)          # only this process needs it: Blender and other children must not inherit it
    try:
        config = Config(llm['base_url'], llm['model'], key, llm['style'], a.openai_effort, a.openai_max_output_tokens)
    except ValueError as ex:
        print(f'OPENAI_API_KEY: {ex}', file=sys.stderr)
        return 2
    try:
        server = create_server(a.jobs_dir, config, a.port)
    except OSError as ex:
        print(f'cannot listen on 127.0.0.1:{a.port} ({ex.strerror or ex}); is the studio already running? use --port', file=sys.stderr)
        return 2
    server.verbose = a.verbose
    url = f'http://127.0.0.1:{a.port}/'
    print(f'Studio at {url}   (Ctrl+C to stop)')
    print(f'  jobs:    {a.jobs_dir}')
    print(f"  blender: {engine.blender_path() or 'NOT FOUND (previews and builds will fail; GLB export still works)'}")
    print(f"  reading: {'key set' if config.api_key else 'no key (automatic reading is off; paste one on the page)'}, provider {a.provider}, model {config.model}, "
          f"{config.style} style at {config.base_url}")
    if not a.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('stopped')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
