# -*- coding: utf-8 -*-
"""公式(1): sales = b0 + b1*t + b2*sin(2*pi*t/6)"""
import numpy as np, pandas as pd
from sklearn.linear_model import LinearRegression

df = pd.read_csv("../sales_data.csv")
t = df["month"].values.reshape(-1,1)
X = np.column_stack([t, np.sin(2*np.pi*t/6)])
y = df["sales"].values
model = LinearRegression().fit(X, y)
print("b0=%.3f b1=%.3f b2=%.3f" % (model.intercept_, *model.coef_))
