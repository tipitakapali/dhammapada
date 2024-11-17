import json

with open("./dhammapada423.txt", "r", encoding="utf-8") as file:
    text = file.read()
verses = text.split("@@")

with open("./dhammapada423.json", "w", encoding="utf-8") as fileout:
    json.dump(verses, fileout, ensure_ascii=False, indent=2)
