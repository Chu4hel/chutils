from chutils.logger import setup_logger


def test_custom_masking():
    # Настраиваем логгер с кастомными паттернами
    logger = setup_logger(
        name="mask_test",
        custom_patterns=[r"user_\d+"],
        use_predefined_patterns=["email"]
    )

    # 1. Тест литеральной маски (через add_mask)
    logger.add_mask("secret_token_123")
    logger.info("My token is secret_token_123")

    # 2. Тест кастомного регулярного выражения
    logger.info("Found user_999 in the system")

    # 3. Тест предустановленного паттерна (email)
    logger.info("Contact me at test@example.com")

    # 4. Тест аргументов
    logger.info("Direct call with %s", "user_123")


if __name__ == "__main__":
    test_custom_masking()
