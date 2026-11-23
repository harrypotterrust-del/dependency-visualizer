"""Тесты генерации PlantUML и кодирования адреса изображения."""

from depviz.plantuml import plantuml_encode, plantuml_text


def test_plantuml_contains_all_nodes_and_edges():
    """Координаты остаются в подписях, связи используют псевдонимы."""
    source = plantuml_text({"A": ["B"], "B": []})
    assert source.startswith("@startuml")
    assert 'rectangle "A" as ' in source
    assert 'rectangle "B" as ' in source
    assert "-->" in source
    assert source.endswith("@enduml")


def test_encoding_is_url_safe():
    """Кодирование не содержит стандартных + / =."""
    encoded = plantuml_encode("@startuml\nA --> B\n@enduml")
    assert encoded
    assert all(character not in encoded for character in "+/=")


def test_quotes_in_labels_are_replaced():
    """Кавычка координат не ломает синтаксис диаграммы."""
    source = plantuml_text({'g:"a': []})
    assert "g:'a" in source
