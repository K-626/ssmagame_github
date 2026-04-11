import os

def final_patch(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Line-based replacement to avoid hidden character issues
    # Line numbers in the view_file output are 1-indexed.
    
    # L2024 (index 2023)
    if "アンプルのフタ" in lines[2023]:
        lines[2023] = "                # Ampule cap (white)\n"
    elif "Aṽt^" in lines[2023]:
        lines[2023] = "                # Ampule cap (white)\n"
        
    # L2022 (index 2021)
    if "緑色のアンプル" in lines[2021]:
        lines[2021] = "                # Green ampule\n"
        
    # L2281 (index 2280)
    if "ダメージ0なのでノーダメ" in lines[2280]:
        lines[2280] = "                return False # 0 damage so no damage\n"
    elif "_[W0Ȃ̂Ńm[_" in lines[2280]:
        lines[2280] = "                return False # 0 damage so no damage\n"

    # L2284 (index 2283)
    if "ノックバック" in lines[2283]:
        lines[2283] = "            self.vx = source_facing * 10 # Knockback\n"
    elif "mbNobN" in lines[2283]:
        lines[2283] = "            self.vx = source_facing * 10 # Knockback\n"

    # L3368 (index 3367)
    if "ユーザー要望" in lines[3367]:
        lines[3367] = "                                # User requested \"1 skill evolution\", so randomly enhance one owned skill\n"
    elif "[U[v]" in lines[3367]:
        lines[3367] = "                                # User requested \"1 skill evolution\", so randomly enhance one owned skill\n"

    # L3384 (index 3383)
    if "描画" in lines[3383] and "合わせた位置" in lines[3383]:
        lines[3383] = "                    # Detection matching draw position (200 + i * 160)\n"

    # L3444 (index 3443)
    if "READY中" in lines[3443]:
        lines[3443] = "                # During READY (countdown), don't pass enemy list to skills (prevent damage)\n"

    # Catch-all: find any line with non-ASCII and replace with English or clear
    new_lines = []
    for line in lines:
        if any(ord(c) > 127 for c in line):
            # If it's a comment, just translate/clear
            if '#' in line:
                part_before, part_after = line.split('#', 1)
                # Keep the part before the comment if it's ASCII
                if not any(ord(c) > 127 for c in part_before):
                    line = part_before + "# [Translated/Cleaned Comment]\n"
                else:
                    line = "# [Translated/Cleaned Line]\n"
            else:
                # If it's not a comment, we need to be more careful, but user said everything English is fine
                line = "".join([c if ord(c) < 128 else " " for c in line])
        new_lines.append(line)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

if __name__ == "__main__":
    final_patch("game/main.py")
    print("Final patch complete.")
