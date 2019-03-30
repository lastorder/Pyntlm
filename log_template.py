# -*- coding: utf-8 -*-

import logging
import logging.config


#LOGGING模块配置
try:
    logging.config.fileConfig("logging.ini")
    log = logging.getLogger()
except Exception as e:
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(module)s %(lineno)d %(message)s')
    log = logging.getLogger()
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(logging.WARNING)
    log.setLevel(logging.WARNING)
    log.addHandler(ch)
    

        
