import datetime

def get_timestamp():
    return (datetime.datetime.now()).timestamp()

# 将时间戳转换成标准格式
def timestamp_to_datetime(timestamp:float):
    return datetime.datetime.fromtimestamp(timestamp)