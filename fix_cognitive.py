import sys

with open("src/antigravity_k/engine/cognitive_loop.py", "r") as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "📝 교훈: " in line or "🔄 재시도 전략: " in line or "</reflection>" in line:
        if (
            line.strip() == 'lines.append("📝 교훈: " + "; ".join(reflection.lessons))'
            or line.strip()
            == 'lines.append(f"🔄 재시도 전략: {reflection.retry_strategy}")'
            or line.strip() == 'lines.append("\n</reflection>")'
            or line.strip() == 'return "".join(lines)'
        ):
            continue
    new_lines.append(line)

with open("src/antigravity_k/engine/cognitive_loop.py", "w") as f:
    f.writelines(new_lines)
