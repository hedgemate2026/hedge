$git = "C:\Program Files\Git\cmd\git.exe"
& $git init
& $git remote add origin https://github.com/hedgemate2026/hedge.git
& $git checkout -b jisheep
& $git add .
& $git commit -m "Initial commit from local HedgeMate"
& $git push -u origin jisheep
