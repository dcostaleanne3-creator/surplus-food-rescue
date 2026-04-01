import os
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder

# Get true path to data file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'food_wastage_data.csv')
data = pd.read_csv(DATA_PATH)

# Create encoders for all categorical columns found in your CSV
label_encoders = {}
categorical_cols = [
    "Type of Food", "Event Type", "Storage Conditions", 
    "Purchase History", "Seasonality", "Preparation Method", 
    "Geographical Location", "Pricing"
]

for col in categorical_cols:
    le = LabelEncoder()
    # Fill any empty cells to prevent encoding errors
    data[col] = data[col].fillna('Unknown')
    data[col] = le.fit_transform(data[col])
    label_encoders[col] = le

# Features (X) and target (y: Wastage Food Amount)
X = data.drop("Wastage Food Amount", axis=1)
y = data["Wastage Food Amount"]

# Train the Random Forest Model
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X, y)

def predict_waste(input_data):
    # Create a dictionary matching ALL 10 columns of your dataset
    full_data = {
        "Type of Food": input_data.get("Type of Food"),
        "Number of Guests": input_data.get("Number of Guests"),
        "Event Type": input_data.get("Event Type"),
        "Quantity of Food": input_data.get("Quantity of Food"),
        "Storage Conditions": "Refrigerated",
        "Purchase History": "Regular",
        "Seasonality": "All Seasons",
        "Preparation Method": "Buffet",
        "Geographical Location": "Urban", # Based on Hubballi context
        "Pricing": "Moderate"
    }
    
    df = pd.DataFrame([full_data])

    # Encode the input values
    for col in categorical_cols:
        try:
            df[col] = label_encoders[col].transform(df[col])
        except ValueError:
            # If a value is new, use the first class as a fallback
            df[col] = 0

    # Ensure the columns are in the exact order the model was trained on
    df = df[X.columns]

    prediction = model.predict(df)[0]
    return round(float(prediction), 2)