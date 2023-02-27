import re
from itertools import zip_longest
from math import ceil
from random import shuffle
from typing import Any, Dict, List
from urllib import parse
import time

import requests
import tabulate


def add_custom_latex_table_format_to_tabulate():
    """Adds new table format into `tabulate`'s `_table_formats` dictionary"""

    # TableFormat.lineabove: see `tabulate` package
    def vertical_line_columns(colwidths, colaligns):
        alignment = { "left": "l", "right": "r", "center": "c", "decimal": "r" }
        tabular_columns_fmt = "|" + "|".join([alignment.get(a, "l") for a in colaligns]) + "|"
        return "\\begin{tabular}{" + tabular_columns_fmt + "}\n\hline"

    tabulate._table_formats["custom_latex"] = tabulate.TableFormat(
        lineabove=vertical_line_columns,
        linebelowheader=tabulate.Line("\\hline", "", "", ""),
        linebetweenrows=tabulate.Line("\\hline", "", "", ""),
        linebelow=tabulate.Line("\\hline\n\\end{tabular}", "", "", ""),
        headerrow=tabulate.DataRow("", "&", "\\\\"),
        datarow=tabulate.DataRow("", "&", "\\\\"),
        padding=1, with_header_hide=None
    )


def show_docstring_at_exception(func):
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            raise Exception(f"{e.args[0]}\n{func.__doc__}")
    return wrapped


@show_docstring_at_exception
def parse_students(filename: str) -> Dict[str, List[str]]:
    """
    Файл со списком групп должен быть в формате:

    ```
    [Название группы 1]
    Студент И. А.
    Студент Б. Ц.
    ...
    [Название группы 2]
    Студент Л. Ы.
    Студент Ц. Б.
    ...
    [Название группы 3]
    ...
    ```
    Допускается список с не сокращенными именем и отчеством (с отсутствием отчества).
    Названия групп не должны повторяться.
    """
    with open(filename, 'r') as f:
        lines = list(filter(len, f.read().splitlines()))
        groups = {}
        current_group = None
        for line in lines:
            if line.startswith("[") and line.endswith("]"):
                group = line[1:-1]
                if group not in groups:
                    groups[group] = []
                    current_group = group
                else:
                    raise Exception(f"Номер группы повторяется, исправьте файл {filename}.")          
            else:
                if current_group is None:
                    raise Exception(f"\nИсправьте файл {filename}.")
                last_name, first_name, patronimic = (
                    splitted
                    if len(splitted := re.sub("\.", "", line).split(" ")) == 3
                    else splitted + [None]
                )
                student = (
                    f"{last_name} {first_name[:1]}. {patronimic[:1]}."
                    if patronimic
                    else f"{last_name} {first_name[:1]}."
                )
                groups[current_group].append(student)
    return groups


@show_docstring_at_exception
def parse_problems(filename: str) -> List[List[str]]:
    """
    Файл со списком задач должен содержать перечисление задач через пробел.

    Одна строка --- одна группа задач.
    """
    with open(filename, 'r') as f:
        lines = list(filter(len, f.read().splitlines()))
        problem_groups = [
            re.split(" +", line)
            for line in lines
        ]
    return problem_groups


def assign_problems(problems: List[str], students_n: int) -> list:
    """
    Случайным образом распределяет задачи из списка `problems`
    на количество студентов `students_n` с минимумом повторов.
    """
    n = ceil(students_n / len(problems))
    multiplied_problems = []
    for _ in range(n):
        p = problems.copy()
        shuffle(p)
        multiplied_problems += p
    return multiplied_problems[:students_n]


def slice_pop(l: List[Any], a: int, b: int=None) -> List[Any]:
    """
    Вырезает из массива указанный промежуток элементов
    """
    start, end = (None, a) if b is None else (a, b)
    l_slice = l[start:end]
    del l[start:end]
    return l_slice


def make_group_tables(
    groups: Dict[str, List[str]],
    problem_groups: List[List[str]]
) -> Dict[str, List[List[str]]]:
    """
    Собирает данные для таблицы с домашним заданием для каждой группы
    """
    total_students_n = sum([len(students) for students in groups.values()])
    problems_assigned = list(map(list, zip(
        *([assign_problems(problems, total_students_n) for problems in problem_groups])
    )))
    group_problems = {
        group: slice_pop(problems_assigned, len(students))
        for group, students in groups.items()
    }
    table_data = {
        group: [
            list((i + 1, student, *(group_problems[group][i])))
            for i, student in enumerate(students)
        ]
        for group, students in groups.items()
    }
    return table_data


def make_tex(
    template: str,
    group: str,
    table: List[List[str]]
) -> str:
    """
    Генерирует .tex файл с домашним заданием для указанной группы.

    При создании шаблона используйте `%(group)s` для указания места вставки названия группы
    и `%(table)s` для указания места вставки таблицы.
    """
    return template % {
        "group": group,
        "table": tabulate.tabulate(table, tablefmt="custom_latex")
    }


def make_homework(make_pdf=False):
    add_custom_latex_table_format_to_tabulate()
    students_filename = (
        input("Введите название файла со списком студентов: ")
        or "students.txt"
    )
    problems_filename = (
        input("Введите название файла со списком задач: ")
        or "problems.txt"
    )
    template_name = (
        input("Введите название файла .tex шаблона: ")
        or "template.tex"
    )
    groups = parse_students(students_filename)
    problem_groups = parse_problems(problems_filename)
    with open(template_name, "r") as f:
        template = f.read()
    group_tables = make_group_tables(groups, problem_groups)
    for group, table in group_tables.items():
        tex = make_tex(template, group, table)
        with open(f"HW_{group.replace(' ', '_')}.tex", "w+") as f:
            f.write(tex)
        if make_pdf:
            url = "https://latexonline.cc/compile?" + parse.urlencode({"text": tex})
            pdf = requests.get(url)
            if pdf.status_code == 200:
                with open(f"HW_{group.replace(' ', '_')}.pdf", "wb+") as f:
                    f.write(pdf.content)
                time.sleep(1.0)
            else:
                print(f"Не удалось выполнить облачную компиляцию pdf для {group}.")


if __name__ == "__main__":
    make_homework()
