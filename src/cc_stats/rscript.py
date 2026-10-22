"""Finding an R that can run the Firth models.

pixi installs an R, but it cannot load logistf (see the README's Gotchas), so
the Firth step needs a CRAN R. Shared by Firth_results.ipynb and
analysis/run_all.py.
"""

import glob
import os
import re
import shutil
import subprocess


def find_rscript():
    """First Rscript that can load logistf: $RSCRIPT, then PATH, then the
    standard Windows / macOS install locations (newest R first). pixi's own R
    is skipped automatically - it is on PATH but cannot load logistf."""
    installed = glob.glob(r"C:\Program Files\R\R-*\bin\Rscript.exe")
    installed.sort(key=lambda p: [int(n) for n in re.findall(r"\d+", os.path.basename(os.path.dirname(os.path.dirname(p))))], reverse=True)
    candidates = [os.environ.get("RSCRIPT"), shutil.which("Rscript"), *installed,
                  "/usr/local/bin/Rscript", "/Library/Frameworks/R.framework/Resources/bin/Rscript"]
    for rscript in dict.fromkeys(c for c in candidates if c and os.path.exists(c)):
        check = subprocess.run([rscript, "-e", "suppressMessages(library(logistf))"], capture_output=True)
        if check.returncode == 0:
            return rscript
    raise FileNotFoundError("No R that can load logistf was found. Install R (>= 4.4) from CRAN, "
                            "run install.packages('logistf') in it, or set the RSCRIPT environment variable.")
