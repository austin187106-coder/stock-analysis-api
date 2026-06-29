"""
產生 PWA 所需的 App 圖示
設計概念：三層堆疊、由寬漸窄的漏斗造型，呼應「月線->週線->日線」三層濾網
逐層篩選、最終收斂出訊號的核心邏輯
"""
from PIL import Image, ImageDraw

BG = (14, 26, 43, 255)        # 深藍墨 --bg
LAYER_1 = (79, 209, 232, 255)  # 亮青 --accent-cyan（月線，最寬）
LAYER_2 = (167, 200, 220, 255)  # 介於兩色之間的過渡藍灰（週線）
LAYER_3 = (242, 184, 75, 255)  # 琥珀 --accent-amber（日線，最窄／訊號收斂）
GAP = (14, 26, 43, 255)        # 與背景同色，製造分層間隙


def draw_funnel(size: int, padding_ratio: float) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG)
    draw = ImageDraw.Draw(img)

    pad = int(size * padding_ratio)
    content_w = size - pad * 2
    content_h = content_w  # 維持方形安全區

    top = pad
    layer_h = content_h // 3
    gap_h = max(2, int(size * 0.012))

    widths = [content_w, int(content_w * 0.66), int(content_w * 0.34)]
    colors = [LAYER_1, LAYER_2, LAYER_3]

    cx = size // 2
    y = top
    for i in range(3):
        w_top = widths[i]
        w_bottom = widths[i + 1] if i < 2 else int(widths[2] * 0.7)
        x0_top, x1_top = cx - w_top // 2, cx + w_top // 2
        x0_bottom, x1_bottom = cx - w_bottom // 2, cx + w_bottom // 2
        y0 = y
        y1 = y + layer_h - gap_h

        draw.polygon(
            [
                (x0_top, y0),
                (x1_top, y0),
                (x1_bottom, y1),
                (x0_bottom, y1),
            ],
            fill=colors[i],
        )
        y += layer_h

    return img


def save_icon(size: int, padding_ratio: float, path: str, flatten_bg=None):
    img = draw_funnel(size, padding_ratio)
    if flatten_bg is not None:
        flat = Image.new("RGB", img.size, flatten_bg)
        flat.paste(img, (0, 0), img)
        flat.save(path)
    else:
        img.save(path)


if __name__ == "__main__":
    out = "/home/claude/stock_analysis_api/webapp/icons"
    save_icon(192, 0.16, f"{out}/icon-192.png")
    save_icon(512, 0.16, f"{out}/icon-512.png")
    save_icon(512, 0.30, f"{out}/icon-maskable-512.png")  # 較大留白，符合maskable安全區
    save_icon(180, 0.16, f"{out}/apple-touch-icon.png", flatten_bg=(14, 26, 43))
    save_icon(32, 0.10, f"{out}/favicon.png")
    print("icons generated")
