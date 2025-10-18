from chutils.decorators import log_function_details

# Просто функция для тестов
@log_function_details
def sample_function(a, b):
    """Складывает два числа."""
    return a + b

def test_log_function_details(mocker):
    """
    Проверяет, что декоратор `log_function_details` корректно логирует вызов.
    """
    # 1. Мокаем (подменяем) логгер, чтобы перехватить его вызовы
    # Логгер в модуле decorators инициализируется с именем 'chutils.decorators'
    mock_log_devdebug = mocker.patch("chutils.decorators.log.devdebug")

    # 2. Мокаем time.perf_counter для предсказуемого времени выполнения
    mocker.patch("chutils.decorators.time.perf_counter", side_effect=[10.0, 12.5])

    # 3. Вызываем нашу декорированную функцию
    result = sample_function(5, 10)

    # 4. Убеждаемся, что сама функция отработала правильно
    assert result == 15

    # 5. Проверяем, что логгер был вызван дважды
    assert mock_log_devdebug.call_count == 2

    # 6. Проверяем содержимое вызовов логгера
    call_args_list = mock_log_devdebug.call_args_list

    # Проверка первого вызова (информация о начале вызова)
    call_before_args = call_args_list[0].args[0]
    assert "Вызов функции: sample_function()" in call_before_args
    assert "с аргументами (5, 10)" in call_before_args

    # Проверка второго вызова (информация о результате)
    call_after_args = call_args_list[1].args[0]
    assert "Функция sample_function() завершилась" in call_after_args
    assert "за 2.5000 с." in call_after_args
    assert "Возвращаемое значение: 15" in call_after_args
