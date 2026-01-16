import base64
with open('my_icon.png', 'rb') as f:
    print(base64.b64encode(f.read()))