#!/usr/bin/env python3

import os
import shutil
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

HOST = os.environ.get("ETIQUETTE_SERVER_HOST", "127.0.0.1")
PORT = int(os.environ.get("ETIQUETTE_SERVER_PORT", "8000"))
TYPST = os.environ.get("ETIQUETTE_TYPST_BIN", "typst")

TYPST_TEMPLATE = r"""
#import "@preview/sheetwise:0.1.0": impose, repeat

#let text = read("label.txt")

#let label = [
    #set std.align(center+horizon)
    #set std.text({{TAILLE_TXT}}pt) 
    #text
]

#impose(
  repeat()[#label],
  paper: "a4",
  trim-size: ({{LARGEUR}}mm, {{HAUTEUR}}mm),
  margin: (14mm, 15mm),
  gap: 0mm,
  cut-mode: "single",
  bleed: 0mm,
  safe: 0mm,
)
"""

HTML_FORM = """<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Étiquettes</title>
    <style>
        body {
            font-family: sans-serif;
            max-width: 600px;
            margin: 4rem auto;
            padding: 0 1rem;
        }

        label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: bold;
        }

        input[type="text"],
        input[type="number"],
        input[type="password"] {
            box-sizing: border-box;
            width: 100%;
            padding: 0.75rem;
            font-size: 1.1rem;
            margin-bottom: 1rem;
        }

        button {
            padding: 0.7rem 1.2rem;
            font-size: 1rem;
            cursor: pointer;
        }

        .error {
            color: #a00;
            background: #fee;
            padding: 1rem;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <h1>Étiquettes</h1>

    <form method="post">
        <label for="label">Texte</label>
        <input
            id="label"
            name="label"
            type="text"
            value="Ma Super Confiture"
            required
            autofocus
            maxlength="1000"
        >

        <label for="largeur">Largeur (en mm)</label>
        <input
            id="largeur"
            name="largeur"
            type="number"
            min="1"
            step="1"
            value="55"
            required
        >

        <label for="hauteur">Hauteur</label>
        <input
            id="hauteur"
            name="hauteur"
            type="number"
            min="1"
            step="1"
            value="15"
            required
        >

        <label for="taille_txt">Taille du texte</label>
        <input
            id="taille_txt"
            name="taille_txt"
            type="number"
            min="1"
            step="1"
            value="16"
            required
        >

        <label for="password">Mot de passe</label>
        <input
            id="password"
            name="password"
            type="password"
            autocomplete="current-password"
            required
        >

        <button type="submit">Générer le PDF</button>
    </form>
</body>
</html>
"""


class LabelHandler(BaseHTTPRequestHandler):
    def send_html(self, content, status=200):
        data = content.encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path != "/":
            self.send_error(404)
            return

        self.send_html(HTML_FORM)

    def do_POST(self):
        if self.path != "/":
            self.send_error(404)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))

            # Prevent unexpectedly large HTTP requests.
            if content_length > 100_000:
                self.send_error(413, "Request too large")
                return

            body = self.rfile.read(content_length)

            form = parse_qs(
                body.decode("utf-8"),
                keep_blank_values=True,
            )

            label_values = form.get("label", [])
            largeur_values = form.get("largeur", [])
            hauteur_values = form.get("hauteur", [])
            taille_txt = form.get("taille_txt", [])
            password = form.get("password", [])

            if not label_values:
                self.send_error(400, "Texte manquant")
                return

            if not largeur_values:
                self.send_error(400, "Missing Largeur")
                return

            if not hauteur_values:
                self.send_error(400, "Missing Hauteur")
                return

            if not taille_txt:
                self.send_error(400, "Missing Taille du texte")
                return

            if password[0] != "confiture":
                self.send_error(403, "Mauvais mot de passe")
                return

            label = label_values[0]
            largeur = int(largeur_values[0])
            hauteur = int(hauteur_values[0])
            taille_txt = int(taille_txt[0])

            if len(label) > 1000:
                self.send_error(400, "Label is too long")
                return

            if largeur < 1:
                self.send_error(400, "Largeur must be a positive integer")
                return

            if hauteur < 1:
                self.send_error(400, "Hauteur must be a positive integer")
                return

            if taille_txt < 1:
                self.send_error(400, "Taille du texte must be a positive integer")
                return

            pdf_data = self.generate_pdf(
                TYPST,
                label,
                largeur,
                hauteur,
                taille_txt,
            )

            filename = "label-sheet.pdf"

            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{filename}"',
            )
            self.send_header("Content-Length", str(len(pdf_data)))
            self.end_headers()
            self.wfile.write(pdf_data)

        except UnicodeDecodeError:
            self.send_error(400, "Invalid UTF-8 request")
        except ValueError:
            self.send_error(400, "Lignes, Colonnes, Taille_txt must be integers")
        except Exception as exc:
            # Do not expose internal details to the browser.
            print(f"Error generating PDF: {exc}")
            self.send_html(
                """<!doctype html>
                <html><body>
                <h1>Error</h1>
                <p>Unable to generate the PDF.</p>
                <p><a href="/">Back</a></p>
                </body></html>""",
                status=500,
            )

    @staticmethod
    def generate_pdf(typst, label, largeur, hauteur, taille_txt):
        # TemporaryDirectory is automatically cleaned up afterward.
        with tempfile.TemporaryDirectory(prefix="label-sheet-") as tmp:
            template_path = os.path.join(tmp, "label.typ")
            label_path = os.path.join(tmp, "label.txt")
            pdf_path = os.path.join(tmp, "label-sheet.pdf")

            # Insert the integer values into the Typst template.
            template = TYPST_TEMPLATE.replace(
                "{{LARGEUR}}",
                str(largeur),
            ).replace(
                "{{HAUTEUR}}",
                str(hauteur),
            ).replace(
                "{{TAILLE_TXT}}",
                str(taille_txt),
            )

            # Write the Typst template.
            with open(template_path, "w", encoding="utf-8") as f:
                f.write(template)

            # The user-provided text is data, not Typst source.
            with open(label_path, "w", encoding="utf-8") as f:
                f.write(label)

            # Do not use shell=True: the user input never becomes
            # part of a shell command.
            result = subprocess.run(
                [
                    typst,
                    "compile",
                    template_path,
                    pdf_path,
                ],
                cwd=tmp,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                check=False,
            )

            if result.returncode != 0:
                error = result.stderr.strip() or result.stdout.strip()
                raise RuntimeError(
                    f"Typst failed with exit code "
                    f"{result.returncode}: {error}"
                )

            if not os.path.isfile(pdf_path):
                raise RuntimeError("Typst did not produce a PDF")

            with open(pdf_path, "rb") as f:
                return f.read()

    def log_message(self, format, *args):
        print(
            f"{self.address_string()} - "
            f"{format % args}"
        )


def main():
    print(f"Starting etiquette server on http://{HOST}:{PORT}/")
    print("Press Ctrl+C to stop.")

    server = HTTPServer((HOST, PORT), LabelHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
