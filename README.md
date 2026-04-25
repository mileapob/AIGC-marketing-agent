# 执行步骤与踩坑点

## 1.增加了evaluate以及quality Agent

### api-key写入APIKEY.env文件

强制加载：

    export $(grep -v '^#' ./APIKEY.env | xargs)

确认

    python -c "
    import os
    keys = ['DEEPSEEK_API_KEY', 'TAVILY_API_KEY', 'OPENAI_API_KEY', 'DASHSCOPE_API_KEY']
    for k in keys:
        v = os.getenv(k, '')
        if not v:
            print(f'{k}: 空')
        else:
            print(f'{k}: OK，末尾={repr(v[-3:])}')
    "

## 2.执行ui中的app.py文件

注意evaluate中原本使用的是doubao的模型，但由于codespace是海外服务器，doubao没有海外服务器，所以使用Qwen-VL-Max进行评估。

    python ui/app.py
