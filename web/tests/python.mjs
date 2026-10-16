// The Python interpreter the tests and npm scripts use: $PYTHON, else `python` on Windows and `python3` elsewhere
// (many Linux and macOS systems have no `python` command).
export const PYTHON = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
