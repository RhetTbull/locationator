# Locationator CLI

Locationator has two components: a server which runs as a menu bar app, and a CLI which can be used to interact with the server. The CLI code is in this directory.

The CLI must be built as a stand alone file with pyinstaller and the resulting `locationator` binary must be placed into the `locationator.app` bundle in the `Contents/resources` directory. The `build.sh` script in the root of the repo will do this for you.
