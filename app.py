# -*- coding: utf-8 -*-
"""
واصل شات - تطبيق Render
ملف التشغيل الرئيسي
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from wasel_chat_STAGE44_REAL_EMAIL_VERIFY_GMAIL_INSIDE import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)