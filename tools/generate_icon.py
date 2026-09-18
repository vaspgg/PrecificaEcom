from pathlib import Path
from PIL import Image, ImageDraw

out = Path('assets')
out.mkdir(exist_ok=True)
S=512
img=Image.new('RGBA',(S,S),(255,255,255,0))
d=ImageDraw.Draw(img)

# Icone baseado no logo oficial enviado: etiqueta azul, carrinho, grafico e seta verde.
navy=(4,38,78,255); blue=(5,101,178,255); green=(31,211,118,255); lime=(82,220,55,255); white=(255,255,255,255)

# etiqueta / corpo principal
tag=[(48,83),(48,220),(121,429),(164,463),(406,463),(449,432),(449,284),(401,244),(335,273),(280,305),(202,323),(137,309),(100,245),(91,211),(91,112),(112,83)]
d.polygon(tag,fill=navy)
# area azul superior para dar leitura semelhante ao logo
d.polygon([(48,83),(48,220),(104,326),(205,315),(286,279),(346,235),(287,176),(216,105),(185,83)],fill=blue)
# furo da etiqueta
d.ellipse((91,111,150,170),fill=white)

# seta de crescimento
pts=[(138,310),(210,301),(285,273),(349,230),(388,190),(366,170),(472,105),(456,219),(431,196),(383,246),(316,290),(240,320),(167,330)]
d.polygon(pts,fill=green)
d.polygon([(366,170),(472,105),(456,219),(431,196),(383,246)],fill=lime)

# carrinho
d.line((105,315,128,315,151,389,247,389,267,333,151,333),fill=white,width=18,joint='curve')
d.ellipse((151,405,184,438),fill=white)
d.ellipse((224,405,257,438),fill=white)

# barras do grafico
for box in [(278,365,318,426),(330,329,370,426),(382,276,422,426)]:
    d.rounded_rectangle(box,radius=7,fill=green)

# leve margem transparente e ICO multiresolucao
img=img.resize((256,256),Image.Resampling.LANCZOS)
img.save(out/'PrecificaEcom.ico',format='ICO',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
print(out/'PrecificaEcom.ico')
