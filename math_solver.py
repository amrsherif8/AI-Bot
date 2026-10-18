"""Mathe-Löser: كل منطق sympy هنا. ملف الـ API (main.py) بس بينادي solve()."""
import itertools
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import datetime

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

MAX_LENGTH = 200       
TIMEOUT_SECONDS = 10  
MAX_HISTORY = 50      


class MathError(ValueError):
    """خطأ برسالة جاهزة تتعرض للمستخدم."""



OPERATIONS = [
    {"id": "solve", "label": "Lösen",
     "hint": "Gleichung lösen. Ein Gleichungssystem trennst du mit ;",
     "needs": ["variable"]},
    {"id": "simplify", "label": "Vereinfachen",
     "hint": "Ausdruck vereinfachen", "needs": []},
    {"id": "expand", "label": "Ausmultiplizieren",
     "hint": "Klammern auflösen", "needs": []},
    {"id": "factor", "label": "Faktorisieren",
     "hint": "In Faktoren zerlegen", "needs": []},
    {"id": "diff", "label": "Ableiten",
     "hint": "Ableitung nach einer Variable", "needs": ["variable"]},
    {"id": "integrate", "label": "Integrieren",
     "hint": "Unbestimmtes Integral, oder bestimmt mit Von und Bis",
     "needs": ["variable", "lower", "upper"]},
    {"id": "limit", "label": "Grenzwert",
     "hint": "Grenzwert an einem Punkt (oo = unendlich)",
     "needs": ["variable", "point"]},
    {"id": "evalf", "label": "Zahlenwert",
     "hint": "Ausdruck als Dezimalzahl berechnen", "needs": []},
]
_OPS_BY_ID = {op["id"]: op for op in OPERATIONS}


_FUNCS = ["sin", "cos", "tan", "cot", "asin", "acos", "atan", "sinh", "cosh",
          "tanh", "exp", "log", "sqrt", "factorial", "floor", "ceiling"]
LOCALS = {name: getattr(sp, name) for name in _FUNCS}
LOCALS.update({"ln": sp.log, "abs": sp.Abs, "Abs": sp.Abs,
               "pi": sp.pi, "e": sp.E, "oo": sp.oo})
GLOBALS = {name: getattr(sp, name) for name in
           ("Integer", "Float", "Rational", "Symbol", "Function",
            "factorial", "factorial2")}
TRANSFORMATIONS = standard_transformations + (
    convert_xor,                     
    implicit_multiplication_application, 
)

_ALLOWED_CHARS = re.compile(r"^[A-Za-z0-9+\-*/^().,=;!\s]+$")
_ATTRIBUTE = re.compile(r"\.\s*[A-Za-z]")
_BIG_POWER = re.compile(r"(\^|\*\*)\s*\(?\s*-?\d{4,}")
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")

_pool = ThreadPoolExecutor(max_workers=4)


_history = []
_history_lock = threading.Lock()
_ids = itertools.count(1)


def operations_list():
    return OPERATIONS


def get_history():
    with _history_lock:
        return list(reversed(_history))  


def clear_history():
    with _history_lock:
        _history.clear()


def _add_history(entry):
    with _history_lock:
        _history.append(entry)
        del _history[:-MAX_HISTORY]



def _txt(value):
    return str(value).replace("**", "^")


def _check(text):
    if not text or not text.strip():
        raise MathError("Bitte gib eine Gleichung ein.")
    if len(text) > MAX_LENGTH:
        raise MathError(f"Die Eingabe ist zu lang (maximal {MAX_LENGTH} Zeichen).")
    if not _ALLOWED_CHARS.match(text):
        raise MathError("Die Eingabe enthält nicht erlaubte Zeichen.")
    if _ATTRIBUTE.search(text):
        raise MathError("Ein Punkt vor Buchstaben ist nicht erlaubt.")
    if _BIG_POWER.search(text):
        raise MathError("Der Exponent ist zu groß.")


def _parse(text):
    text = text.strip()
    if not text:
        raise MathError("Eine Seite der Gleichung ist leer.")
    try:
        result = parse_expr(text, local_dict=dict(LOCALS),
                            global_dict=dict(GLOBALS),
                            transformations=TRANSFORMATIONS)
    except Exception:
        raise MathError(f"Ich kann diesen Ausdruck nicht verstehen: {text}") from None
    if not isinstance(result, sp.Expr):
        raise MathError(f"Ich kann diesen Ausdruck nicht verstehen: {text}")
    return result


def _symbol(name):
    name = name.strip()
    if not _NAME.match(name):
        raise MathError(f"„{name}“ ist kein gültiger Variablenname.")
    return sp.Symbol(name)


def _need_variable(expr, name):
    if name:
        return _symbol(name)
    symbols = sorted(expr.free_symbols, key=str)
    if len(symbols) == 1:
        return symbols[0]
    if not symbols:
        raise MathError("Keine Variable gefunden.")
    names = ", ".join(str(s) for s in symbols)
    raise MathError(f"Mehrere Variablen gefunden ({names}). Bitte wähle eine Variable.")



def _solve(text, variable):
    parts = [p.strip() for p in text.split(";") if p.strip()]
    if not parts:
        raise MathError("Bitte gib eine Gleichung ein.")

    exprs, shown = [], []
    for part in parts:
        if part.count("=") > 1:
            raise MathError('Pro Gleichung ist nur ein "=" erlaubt.')
        if "=" in part:
            left, right = (_parse(side) for side in part.split("="))
        else:
            left, right = _parse(part), sp.Integer(0)   # من غير = يعني = 0
        exprs.append(left - right)
        shown.append(f"{sp.latex(left)} = {sp.latex(right)}")
    input_latex = r" \quad ; \quad ".join(shown)

    all_symbols = sorted(set().union(*(e.free_symbols for e in exprs)), key=str)
    if variable:
        var = _symbol(variable)
        if var not in all_symbols:
            raise MathError(f"Die Variable {var} kommt in der Gleichung nicht vor.")
        var_list = [var]
    elif len(all_symbols) <= 1 or len(exprs) > 1:
        var_list = all_symbols
    else:
        names = ", ".join(str(s) for s in all_symbols)
        raise MathError(f"Mehrere Variablen gefunden ({names}). Bitte wähle eine Variable.")
    if not var_list:
        raise MathError("Keine Variable gefunden.")

    no_solution = ("Keine Lösung", r"\text{Keine Lösung}", input_latex)

    if len(exprs) == 1 and len(var_list) == 1:
        var = var_list[0]
        solutions = sp.solve(exprs[0], var)
        if not solutions:
            return no_solution
        result = ";  ".join(f"{var} = {_txt(s)}" for s in solutions)
        latex = r",\quad ".join(f"{sp.latex(var)} = {sp.latex(s)}" for s in solutions)
        return result, latex, input_latex

    solutions = sp.solve(exprs, var_list, dict=True)
    if not solutions:
        return no_solution
    lines, latex_lines = [], []
    for sol in solutions:
        lines.append(", ".join(f"{k} = {_txt(v)}" for k, v in sol.items()))
        latex_lines.append(r",\; ".join(f"{sp.latex(k)} = {sp.latex(v)}" for k, v in sol.items()))
    return "\n".join(lines), r" \quad\text{oder}\quad ".join(latex_lines), input_latex


def _expression_op(text, operation, variable, point, lower, upper):
    if "=" in text or ";" in text:
        raise MathError('Hier bitte kein "=" verwenden. Für Gleichungen wähle „Lösen“.')
    expr = _parse(text)
    input_latex = sp.latex(expr)
    suffix, latex_suffix = "", ""

    if operation == "simplify":
        res = sp.simplify(expr)
    elif operation == "expand":
        res = sp.expand(expr)
    elif operation == "factor":
        res = sp.factor(expr)
    elif operation == "diff":
        res = sp.diff(expr, _need_variable(expr, variable))
    elif operation == "integrate":
        var = _need_variable(expr, variable)
        if lower or upper:
            if not (lower and upper):
                raise MathError("Für ein bestimmtes Integral brauche ich „Von“ und „Bis“.")
            res = sp.integrate(expr, (var, _parse(lower), _parse(upper)))
        else:
            res = sp.integrate(expr, var)
            suffix, latex_suffix = " + C", " + C"
        if res.has(sp.Integral):
            raise MathError("Dieses Integral kann ich nicht lösen.")
    elif operation == "limit":
        var = _need_variable(expr, variable)
        target = _parse(point) if point else sp.Integer(0)
        res = sp.limit(expr, var, target)
        if res.has(sp.Limit):
            raise MathError("Diesen Grenzwert kann ich nicht berechnen.")
    elif operation == "evalf":
        if expr.free_symbols:
            raise MathError("Der Ausdruck enthält Variablen. Für einen Zahlenwert brauche ich nur Zahlen.")
        res = sp.N(expr, 15)
    else:
        raise MathError("Diese Rechenart gibt es nicht.")

    return _txt(res) + suffix, sp.latex(res) + latex_suffix, input_latex


def _run(expression, operation, variable, point, lower, upper):
    if operation not in _OPS_BY_ID:
        raise MathError("Diese Rechenart gibt es nicht.")
    _check(expression)
    if operation == "solve":
        return _solve(expression, variable)
    return _expression_op(expression, operation, variable, point, lower, upper)


# ---------- الدالة اللي الـ API بينادي عليها ----------
def solve(expression, operation, variable=None, point=None, lower=None, upper=None):
    expression = (expression or "").strip()
    variable, point = (variable or "").strip() or None, (point or "").strip() or None
    lower, upper = (lower or "").strip() or None, (upper or "").strip() or None

    future = _pool.submit(_run, expression, operation, variable, point, lower, upper)
    try:
        result, latex, input_latex = future.result(timeout=TIMEOUT_SECONDS)
    except FutureTimeout:
        raise MathError("Die Berechnung dauert zu lange (mehr als 10 Sekunden).") from None
    except MathError:
        raise
    except Exception as error:
        raise MathError(f"Das konnte ich nicht berechnen ({type(error).__name__}).") from None

    entry = {
        "id": next(_ids),
        "time": datetime.now().strftime("%H:%M:%S"),
        "expression": expression,
        "operation": operation,
        "operation_label": _OPS_BY_ID[operation]["label"],
        "result": result,
        "latex": latex,
        "input_latex": input_latex,
        "params": {"variable": variable, "point": point, "lower": lower, "upper": upper},
    }
    _add_history(entry)
    return entry
