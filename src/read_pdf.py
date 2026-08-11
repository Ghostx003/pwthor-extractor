import glob, re
files = glob.glob('e:/projects/general scripts/PWTHOR AUTO DOWNLOAD/downloads/APTITUDE/*.pdf')
with open(files[0], 'r', encoding='utf-8', errors='ignore') as f:
    html = f.read()

title = re.search(r'<title>(.*?)</title>', html)
print('Title:', title.group(1) if title else 'No title')

meta = re.search(r'<meta[^>]*description[^>]*content=\"([^\"]*)\"', html, re.IGNORECASE)
print('Description:', meta.group(1) if meta else 'No description')
