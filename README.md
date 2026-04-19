# 修改后的Agent

## 1.增加了evaluate以及
export DASHSCOPE_API_KEY=$(grep DASHSCOPE_API_KEY ./APIKEY.env | cut -d'=' -f2 | tr -d '\n')

python -c "import os; key=os.getenv('DASHSCOPE_API_KEY',''); print(repr(key[-5:]))"

## 2.api-key写入APIKEY.env文件

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
