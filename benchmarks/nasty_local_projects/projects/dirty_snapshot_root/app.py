def normalize(text: str) -> str:
    return text.strip().lower()


def main() -> None:
    print(normalize(" Example "))


if __name__ == "__main__":
    main()
