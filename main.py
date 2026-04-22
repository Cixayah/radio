import argparse


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

    if args.cli:
        launch_cli()
    else:
        launch_gui()


if __name__ == "__main__":
    main()
