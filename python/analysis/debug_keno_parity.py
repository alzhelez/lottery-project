#!/usr/bin/env python3
"""Отладка четности для Keno"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lottery.drawfile import load_game_data
from lottery.games import get_game

game = get_game("keno2")
data = load_game_data(game)

X = data.matrices[0]
spec = data.fmt.blocks[0]
T, N = X.shape
k = spec.count

print(f"Game: {game.title}")
print(f"Spec: {spec}")
print(f"Range: {spec.lo} to {spec.hi}")
print(f"Matrix shape: {T} x {N}")
print(f"Count per draw: {k}")

# Анализ первых 10 тиражей
print(f"\nПервые 10 тиражей:")
for t in range(min(10, T)):
    numbers = []
    for i in range(N):
        if X[t, i] == 1:
            numbers.append(i + spec.lo)

    even = sum(1 for n in numbers if n % 2 == 0)
    odd = len(numbers) - even
    print(f"  Тираж {t+1}: {sorted(numbers)[:5]}... | Четных: {even}, Нечетных: {odd}")

# Общий подсчет
print(f"\nПолный подсчет по всем {T} тиражам:")
even_total = 0
odd_total = 0

for t in range(T):
    for i in range(N):
        if X[t, i] == 1:
            num = i + spec.lo
            if num % 2 == 0:
                even_total += 1
            else:
                odd_total += 1

total = even_total + odd_total
print(f"Четных: {even_total} ({100*even_total/total:.2f}%)")
print(f"Нечетных: {odd_total} ({100*odd_total/total:.2f}%)")
print(f"Всего: {total}")
print(f"Ожидается: {T * k} = {T} * {k}")

if total != T * k:
    print(f"⚠️ ОШИБКА: total ({total}) != T*k ({T*k})")
