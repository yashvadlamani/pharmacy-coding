"""Deploy the workspace to Azure App Service.

    python deploy.py                  # zip the app and deploy it
    python deploy.py --configure      # also set the app settings (first deployment, or after rotating a secret)

--configure reads the storage connection string and the workspace password hash from .env. If .env has no
password yet it generates one and writes both the password and its hash there; the password itself is never
sent to Azure. Requires the Azure CLI, logged in.
"""
import argparse
import json
import secrets
import subprocess
import tempfile
import zipfile
from pathlib import Path

from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parent
RESOURCE_GROUP = "pharmacy-coding-rg"
APP = "pharmcoding-workspace-f946de69"
INCLUDE = ["app.py", "requirements.txt", "pharmacy_coding", "templates", "static"]
STARTUP = "gunicorn --bind=0.0.0.0 --timeout 120 --workers 2 app:app"


def az(*args):
    subprocess.run(["az", *args, "-o", "none"], check=True, shell=True)


def read_env():
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def configure():
    env = read_env()
    if not env.get("WORKSPACE_PASSWORD_HASH"):
        password = secrets.token_urlsafe(12)
        env["WORKSPACE_PASSWORD"] = password
        env["WORKSPACE_PASSWORD_HASH"] = generate_password_hash(password)
        with open(ROOT / ".env", "a", encoding="utf-8") as f:
            f.write(f"WORKSPACE_PASSWORD={password}\nWORKSPACE_PASSWORD_HASH={env['WORKSPACE_PASSWORD_HASH']}\n")
        print("Generated a workspace password; it is in .env as WORKSPACE_PASSWORD")
    settings = {"AZURE_STORAGE_CONNECTION_STRING": env["AZURE_STORAGE_CONNECTION_STRING"],
                "WORKSPACE_PASSWORD_HASH": env["WORKSPACE_PASSWORD_HASH"],
                "FLASK_SECRET_KEY": secrets.token_urlsafe(32),
                "SCM_DO_BUILD_DURING_DEPLOYMENT": "true"}
    # a settings file keeps the values off the command line, where "$" and ";" would need escaping
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "settings.json"
        path.write_text(json.dumps(settings), encoding="utf-8")
        az("webapp", "config", "appsettings", "set", "-g", RESOURCE_GROUP, "-n", APP, "--settings", f"@{path}")
    az("webapp", "config", "set", "-g", RESOURCE_GROUP, "-n", APP, "--startup-file", STARTUP,
       "--min-tls-version", "1.2", "--ftps-state", "Disabled")


def deploy():
    with tempfile.TemporaryDirectory() as folder:
        archive = Path(folder) / "app.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for name in INCLUDE:
                path = ROOT / name
                files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]
                for file in files:
                    if "__pycache__" not in file.parts:
                        z.write(file, file.relative_to(ROOT).as_posix())
        az("webapp", "deploy", "-g", RESOURCE_GROUP, "-n", APP, "--src-path", str(archive), "--type", "zip")
    print(f"Deployed to https://{APP}.azurewebsites.net")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--configure", action="store_true", help="set the app settings before deploying")
    if parser.parse_args().configure:
        configure()
    deploy()
