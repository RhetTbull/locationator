# Source files for Locationator 

The source files are organized as individual python modules (files), not as a package. Any files added to `src` directory must also be added as in the `setup.py` `DATA_FILES` list to be included by py2app in the app bundle.

`locationator.py` is the main module and is the entry point for the app. It contains the `Locationator` class which is the main app class.
