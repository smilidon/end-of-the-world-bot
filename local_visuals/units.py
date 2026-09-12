# SPDX-License-Identifier: GPL-3.0-only
import math,re
MILE=1609.344
FOOT=0.3048
def distance(meters,total=False):
 value=float(meters)
 if not math.isfinite(value) or value<0:raise ValueError('Invalid distance')
 # Nearest hundredth for totals; internal meters remain unchanged.
 if total:return f'{value/MILE:.2f} mi'
 return f'{value/MILE:.2f} mi' if value>=MILE/10 else f'{value/FOOT:.0f} ft'
def imperial_text(text):
 return re.sub(r'(?<![\w.])(\d+(?:\.\d+)?)\s*(km|m)\b',lambda m:distance(float(m[1])*(1000 if m[2]=='km' else 1)),text)
