import matplotlib.pyplot as plt
import networkx as nx

# Создание графа
G = nx.DiGraph()

# Добавляем таблицы
tables = [
    "users", "characters", "locations", "creatures", "inventory", "items", "logs", "loot_entries", "loot_groups"
]
G.add_nodes_from(tables)

# Добавляем связи между таблицами (фантазия на основе твоей структуры)
relations = [
    ("users", "characters"), 
    ("users", "logs"),
    ("characters", "inventory"),
    ("inventory", "items"),
    ("creatures", "locations"),
    ("creatures", "loot_entries"),
    ("loot_entries", "loot_groups"),
    ("loot_entries", "items")
]
G.add_edges_from(relations)

# Рисуем граф
pos = nx.spring_layout(G)  # Расположение узлов
plt.figure(figsize=(10, 8))  # Размер фигуры
nx.draw(G, pos, with_labels=True, node_size=3000, node_color="skyblue", font_size=10, font_weight="bold", arrows=True)

# Отображаем
plt.title("Схема взаимодействия таблиц базы данных")
plt.show()
