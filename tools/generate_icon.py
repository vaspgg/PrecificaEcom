from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

out = Path('assets')
out.mkdir(exist_ok=True)
size = 256
img = Image.new('RGBA', (size, size), (15, 23, 42, 255))
d = ImageDraw.Draw(img)
# Etiqueta de preco
d.rounded_rectangle((38, 54, 218, 202), radius=30, fill=(15, 118, 110, 255))
d.ellipse((58, 78, 82, 102), fill=(244, 246, 248, 255))
# P estilizado, legivel em tamanhos pequenos
try:
    font = ImageFont.truetype('C:/Windows/Fonts/seguisb.ttf', 112)
except Exception:
    font = ImageFont.load_default()
d.text((92, 62), 'P', font=font, fill=(255, 255, 255, 255))
# seta de crescimento
d.line((70, 181, 112, 148, 143, 163, 190, 116), fill=(255,255,255,255), width=11)
d.polygon([(190,116),(166,119),(187,140)], fill=(255,255,255,255))
img.save(out / 'PrecificaEcom.ico', format='ICO', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
print(out / 'PrecificaEcom.ico')
