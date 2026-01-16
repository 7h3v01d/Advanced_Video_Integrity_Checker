# **Base64 Icon Encoder (lite)**

A lightweight Python utility to convert image files into Base64-encoded strings. This is ideal for developers who want to embed icons or small images directly into HTML, CSS, or JSON files to reduce external HTTP requests.

## 🚀 **How It Works**
The script reads a local image file in binary mode, encodes it using the base64 library, and outputs the resulting string to your terminal.

**Prerequisites**
- Python 3.x installed on your system.
- An image file named my_icon.png located in the same directory as the script.

**Usage**
1. Place your icon in the project folder and ensure it is named my_icon.png.
2. Run the script from your terminal:

```Bash
python encode_icon.py
```
Copy the generated string from the console output.

## 🛠️ **Customization**
If you want to encode a different file or use a different format (like .jpg or .svg), simply update the filename in the script:

```Python
# Change 'my_icon.png' to your preferred filename
with open('your_image_here.jpg', 'rb') as f:
```

## 💡 **Why use Base64?**
- Single File Portability: Keep your images inside your code files.
- Performance: Reduces the number of HTTP requests for small icons.
- Email Templates: Useful for embedding logos in HTML emails where external hosting might be blocked.
