"""
Single source of truth for the app version — compared against update
manifests (a_updater.py) and stamped into issue reports (a_issue_reporter.py).
Bump this by hand as part of cutting a release; Phase 6 packaging will wire
it into the installer/build metadata too.
"""
VERSION = "2.1.0"
