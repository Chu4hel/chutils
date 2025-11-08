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
    # 1. Создаем мок-логгер и подменяем геттер, чтобы он возвращал наш мок
    mock_logger = mocker.Mock()
    mocker.patch("chutils.decorators._get_logger", return_value=mock_logger)

    # 2. Мокаем time.perf_counter для предсказуемого времени выполнения
    mocker.patch("chutils.decorators.time.perf_counter", side_effect=[10.0, 12.5])

    # 3. Вызываем нашу декорированную функцию
    result = sample_function(5, 10)

    # 4. Убеждаемся, что сама функция отработала правильно
    assert result == 15

    # 5. Проверяем, что метод devdebug нашего мок-логгера был вызван дважды
    assert mock_logger.devdebug.call_count == 2

    # 6. Проверяем содержимое вызовов логгера
    call_args_list = mock_logger.devdebug.call_args_list

    # Проверка первого вызова (информация о начале вызова)
    # call_args_list[0] -> call('формат %s', 'аргумент1', 'аргумент2')
    # .args -> ('формат %s', 'аргумент1', 'аргумент2')
    call_before = call_args_list[0]
    assert call_before.args[0] == "Вызов функции: %s() с аргументами %s и %s"
    assert call_before.args[1] == "sample_function"
    assert call_before.args[2] == (5, 10)
    assert call_before.args[3] == {}

    # Проверка второго вызова (информация о результате)
    call_after = call_args_list[1]
    assert call_after.args[0] == "Функция %s() завершилась за %.4f с. Возвращаемое значение: %s"
    assert call_after.args[1] == "sample_function"
    assert call_after.args[2] == 2.5
    assert call_after.args[3] == 15
