import argparse
import os
import shutil


def clean_temp_audios():
    temp_audios_path = os.path.abspath(os.path.join("radio_capture", "temp_audios"))
    os.makedirs(temp_audios_path, exist_ok=True)

    for entry_name in os.listdir(temp_audios_path):
        entry_path = os.path.join(temp_audios_path, entry_name)
        try:
            if os.path.isdir(entry_path) and not os.path.islink(entry_path):
                shutil.rmtree(entry_path)
            else:
                os.remove(entry_path)
        except FileNotFoundError:
            continue
        except OSError as exc:
            print(f"⚠️  Não foi possível limpar {entry_path}: {exc}")


def launch_cli():
    from app import AdDetector

    AdDetector().run()


def launch_gui():
    from app.ui import launch_app

    launch_app()


def main():
    parser = argparse.ArgumentParser(description="Radio Ad Detector")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Executa no modo de terminal em vez da interface gráfica.",
    )
    args = parser.parse_args()

    clean_temp_audios()

    if args.cli:
        launch_cli()
    else:
        launch_gui()


if __name__ == "__main__":
    main()
