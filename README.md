# Xed Autosave

Autosave plugin for [Xed](https://github.com/linuxmint/xed), the Linux Mint
text editor.

The plugin saves changed documents shortly after editing stops. Existing files
are saved through Xed's own save mechanism. New, unnamed documents are written
to a private autosave directory and can be restored on the next Xed start.

## Features

- Saves changed documents after 500 ms of inactivity.
- Saves existing files in place through Xed, so the editor stays aware of the
  save operation.
- Stores new unsaved documents in `~/.xed/autosave`.
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
cp xed-autosave.plugin ~/.local/share/xed/plugins/
cp -r xed_autosave ~/.local/share/xed/plugins/
```

Then restart Xed and enable the plugin:

```text
Edit -> Preferences -> Extensions -> Autosave
```

Depending on the desktop language, the plugin may appear as `Autosave` or
`Автосохранение`.

## Usage

After the plugin is enabled, no extra action is required.

For an existing file, edit the document and stop typing. After 500 ms, the
plugin asks Xed to save the file.

For a new unnamed document, edit the document and stop typing. After 500 ms, the
plugin writes an autosaved copy to:

```text
~/.xed/autosave
```

The autosave index is stored in:

```text
~/.xed/autosave/index.json
```

## Debug Logging

Debug logging is disabled by default. To enable it:

```bash
XED_AUTOSAVE_DEBUG=1 xed --standalone
```

The default log file is:

```text
~/.xed/autosave/debug.log
```

You can choose another log file:

```bash
XED_AUTOSAVE_DEBUG=1 XED_AUTOSAVE_DEBUG_LOG=/tmp/xed-autosave.log xed --standalone
```

This repository also includes a helper script for local testing:

```bash
./xed.local.sh
```

It starts Xed in standalone mode with debug logging enabled.

## Manual Checks

Useful checks after changing the plugin:

1. Start Xed through `./xed.local.sh`.
2. Create a new unnamed document, type text, wait briefly, and confirm that an
   `unsaved-*.txt` file appears in `~/.xed/autosave`.
3. Close only that tab and confirm that the corresponding `unsaved-*.txt` file
   and `index.json` entry are removed.
4. Create another unnamed document, wait for autosave, close the whole Xed
   window, and confirm that the document is restored on the next start.
5. Open a normal saved file, edit it, wait briefly, and confirm that Xed does
   not show an external-change warning or a save confirmation on close.

## Development

Run the test suite with the standard library test runner:

```bash
python3 -m unittest discover -s tests -q
```

The tests cover storage behavior, delayed scheduling, debug logging, document
identity tracking, configuration, and the Xed save wrapper.

## Notes

Xed's Python plugin API does not expose every internal save operation directly.
For already saved files, this plugin calls Xed's native save command from
`libxed.so`. If that native command cannot be loaded, the plugin falls back to a
direct file write as a last resort.

