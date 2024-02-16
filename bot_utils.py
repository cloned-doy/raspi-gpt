import json, time

def config_reader(file_path):
    try:
        with open(file_path, 'r') as f:
            results = json.load(f)
            return results
    except:
        raise Exception(f"Error reading the {file_path} file. Stopping the app.")

tokens_file = "xtokens.json"
chat_ids_file = "xchat_ids.json"

def continous_config_saver(object, file_path, cache_timeout):
    try:
        while True:        
            with open(file_path, 'w') as f:
                json.dump(object, f)
            time.sleep(cache_timeout)
    except:
        raise Exception(f"Error saving the {str(object)} file. Stopping the app.")


def add_new_xtokens(xtokens, token_name, token):    
    new_dict = {
        "total_used": 0,
        "grand_total_used": 0,        
        "last_used": 0,
        "token": token,
        }
    
    xtokens[token_name] = new_dict
    return xtokens

import time

current_time_minutes = int(time.time() / 60)
print(current_time_minutes)