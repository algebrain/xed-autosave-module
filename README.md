# Hadron Autosave

> **Warning!**
>
> This plugin can be dangerous. If you accidentally change a file, the change
> may be saved to disk automatically before you notice it. Use it only if you
> are comfortable with automatic in-place saves.

Hadron Autosave plugin for [Xed](https://github.com/linuxmint/xed), the Linux
Mint text editor.

The plugin saves changed documents shortly after editing stops. Before an
existing file is autosaved, the previous on-disk version is copied to a private
backup directory. New, unnamed documents are written to a private autosave
directory and can be restored on the next Xed start.

## Features

- Saves changed documents after 500 ms of inactivity.
- Saves existing files in place only after creating a backup of the previous
  on-disk version.
- Shows a warning bar for autosaved existing files.
- Lets you restore the previous version or accept the current autosaved version.
- Stores new unsaved documents in `~/.xed/hadron-autosave`.
- Restores autosaved unsaved documents when the plugin starts.
- Deletes an autosaved unsaved document when its tab is explicitly closed.
- Keeps autosaved unsaved documents when the whole Xed window is closed, so
  they can be restored later.
- Optional file-based debug logging for manual testing.

## Installation

Copy the plugin metadata file and package directory into Xed's user plugin
directory:

```bash
mkdir -p ~/.local/share/xed/plugins
cp hadron-autosave.plugin ~/.local/share/xed/plugins/
cp -r hadron_autosave ~/.local/share/xed/plugins/
```

Then restart Xed and enable the plugin:

```text
Edit -> Preferences -> Extensions -> Hadron Autosave
```

Depending on the desktop language, the plugin may appear as `Hadron Autosave`
or `Адронное автосохранение`.

## Usage

After the plugin is enabled, no extra action is required.

For an existing file, edit the document and stop typing. After 500 ms, the
plugin creates a backup of the current file on disk, then asks Xed to save the
edited document.

The backup is stored under:

```text
~/.xed/hadron-autosave/backups
```

After autosave, a warning bar appears above the text. It shows when the backup
was last modified and provides two actions:

- `Restore` restores the previous version from the backup, removes the backup,
  and hides the warning bar.
- `Accept Changes` keeps the current autosaved file, removes the backup, and
  hides the warning bar.

If the current Xed/GTK environment supports confirmation dialogs, both actions
ask for confirmation first. If a backup exists when Xed starts, the original
file is opened again and the warning bar is shown. If the file is opened
manually while the backup still exists, the warning bar is shown as well.

For a new unnamed document, edit the document and stop typing. After 500 ms, the
plugin writes an autosaved copy to:

```text
~/.xed/hadron-autosave
```

The autosave index is stored in:

```text
~/.xed/hadron-autosave/index.json
```

## Debug Logging

Debug logging is disabled by default. To enable it:

```bash
XED_AUTOSAVE_DEBUG=1 xed --standalone
```

The default log file is:

```text
~/.xed/hadron-autosave/debug.log
```

You can choose another log file:

```bash
XED_AUTOSAVE_DEBUG=1 XED_AUTOSAVE_DEBUG_LOG=/tmp/hadron-autosave-debug.log xed --standalone
```

This repository also includes a helper script for local testing:

```bash
./xed-debug.sh
```

It starts Xed in standalone mode with debug logging enabled.

## Manual Checks

Useful checks after changing the plugin:

1. Start Xed through `./xed-debug.sh`.
2. Create a new unnamed document, type text, wait briefly, and confirm that an
   `unsaved-*.txt` file appears in `~/.xed/hadron-autosave`.
3. Close only that tab and confirm that the corresponding `unsaved-*.txt` file
   and `index.json` entry are removed.
4. Create another unnamed document, wait for autosave, close the whole Xed
   window, and confirm that the document is restored on the next start.
5. Open a normal saved file, edit it, wait briefly, and confirm that a backup
   appears in `~/.xed/hadron-autosave/backups`.
6. Confirm that the warning bar shows the backup time and has `Restore` and
   `Accept Changes` buttons.
7. Use `Restore` and confirm that the previous file contents return and the
   backup is removed.
8. Repeat the edit and use `Accept Changes`; confirm that the backup is removed
   and the next edit creates a new backup.
9. Leave a backup unresolved, close Xed, start Xed again, and confirm that the
   original file opens with the warning bar.

## Development

Run the test suite with the standard library test runner:

```bash
python3 -m unittest discover -s tests -q
```

Run the test suite with coverage:

```bash
.venv/bin/python -m coverage run -m unittest discover -s tests -q
.venv/bin/python -m coverage report -m
```

The tests cover storage behavior, backup behavior, delayed scheduling, debug
logging, document identity tracking, configuration, and the Xed save wrapper.

## Notes

Xed's Python plugin API does not expose every internal save operation directly.
For already saved files, this plugin calls Xed's native save command from
`libxed.so`. If that native command cannot be loaded, the plugin falls back to a
direct file write as a last resort.
