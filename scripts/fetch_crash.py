import requests, json, pandas as pd
U="https://services2.arcgis.com/Ne8d9gKn5SJ3eAaw/arcgis/rest/services/DfT_16_21/FeatureServer/0/query"
F="Accident_Index,Severity,Accident_Year,Date,Easting,Northing,Casulaity_Type,Casuality_Type_Group,Vehicle_Type,Vehicle_Type_Group,Junction_Detail,Speed_Limit,No_of_Casualities"
rows=[]; off=0
while True:
    r=requests.get(U,params=dict(where="1=1",outFields=F,returnGeometry="false",f="json",resultOffset=off,resultRecordCount=2000,orderByFields="OBJECTID"),timeout=60).json()
    fs=r.get('features',[]); rows+=[f['attributes'] for f in fs]
    if len(fs)<2000: break
    off+=2000
df=pd.DataFrame(rows); print(len(df), df.Accident_Index.nunique())
print(df.Severity.value_counts().to_dict()); print(df.Accident_Year.value_counts().sort_index().to_dict())
print(df.Casuality_Type_Group.value_counts().head(10).to_dict()); print(df.Vehicle_Type_Group.value_counts().head(10).to_dict())
bike=df[(df.Casuality_Type_Group.astype(str).str.contains('ycl',case=False))|(df.Vehicle_Type_Group.astype(str).str.contains('ycl',case=False))|(df.Vehicle_Type.astype(str).str.contains('edal',case=False))|(df.Casulaity_Type.astype(str).str.contains('ycl',case=False))]
print('rows mentioning bikes',len(bike),'collisions',bike.Accident_Index.nunique())
print(bike.Casulaity_Type.value_counts().head(5).to_dict(), bike.Vehicle_Type.value_counts().head(5).to_dict())
df.to_pickle('data/crash_rows.pkl')
