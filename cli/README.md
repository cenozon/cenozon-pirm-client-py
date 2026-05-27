# cenozon-pirm-cli

The `pirm-dgw` command-line interface for the Cenozon PIRM Data Gateway.

This package is an opt-in install layered on top of
[`cenozon-pirm-client`](https://github.com/cenozon/cenozon-pirm-client-py). The
library install never ships a script entry; you only get `pirm-dgw` when you
explicitly install this package.

## Install

```sh
# uv tool — installs the CLI globally without polluting any project venv
uv tool install 'cenozon-pirm-cli @ git+https://github.com/cenozon/cenozon-pirm-client-py.git#subdirectory=cli'

# inside a project venv
uv add 'cenozon-pirm-cli @ git+https://github.com/cenozon/cenozon-pirm-client-py.git#subdirectory=cli'
```

## Usage

```sh
pirm-dgw ping
pirm-dgw whoami
pirm-dgw list custom
pirm-dgw list asset-manager --group my-group
pirm-dgw fetch custom "Master Pipeline Modified" -f csv -o out.csv
pirm-dgw fetch asset-manager 12345 -f xlsx -o out.xlsx
pirm-dgw schema custom ili
```

Credentials come from a `.env` file (default `./.env`) or flags. See
`pirm-dgw --help` for the full surface.

Downloads stream to disk with a progress indicator on a TTY; output is
tab-separated when stdout is piped.
