import os
from fastapi import FastAPI, Header, HTTPException, Depends
from typing import Optional, List
import pyodbc
import msal
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Add this block after creating 'app'
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yellow-coast-0ea82d100.7.azurestaticapps.net"],  # Replace "*" with your actual Azure Static Web App URL for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuration ---
DB_CONNECTION_STRING = (
    "Driver={ODBC Driver 18 for SQL Server};"
    "Server=tcp:newen-server.database.windows.net,1433;"
    "Database=newen_traceability_db;"
    "UID=omsingh;"
    "PWD=Singhisblink7621;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
    "Connection Timeout=30;"
)

# Azure AD Config (for token verification)
CLIENT_ID = "YOUR_CLIENT_ID"
TENANT_ID = "YOUR_TENANT_ID"

# --- Models ---
class Component(BaseModel):
    sectionName: str
    componentName: str
    make: str
    serialNumber: str
    warranty: Optional[str]

class PanelResponse(BaseModel):
    projectName: str
    panel_sr_no: str
    startDate: str
    verifiedBy: str
    companyName: str = "Newen Systems Pvt Ltd"
    additionalData: Optional[dict] = None
    components: Optional[List[Component]] = None

# --- Helper Functions ---
def verify_token(authorization: str = Header(None)):
    if not authorization:
        return None
    # In a production app, use msal to validate the token signature and claims
    # For now, we assume if a token is present, we attempt an authenticated fetch
    return authorization.split(" ")[1]

def get_db_connection():
    return pyodbc.connect(DB_CONNECTION_STRING)

# --- Endpoints ---

@app.get("/get_panel_details", response_model=PanelResponse)
def get_panel_details(id: str, token: Optional[str] = Depends(verify_token)):
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Fetch Public Data
    cursor.execute("SELECT ProjectName, SerialNumber, StartDate, VerifiedBy FROM Panels WHERE SerialNumber = ?", id)
    row = cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Panel not registered in system")

    response = PanelResponse(
        projectName=row.ProjectName,
        panel_sr_no=row.SerialNumber,
        startDate=str(row.StartDate),
        verifiedBy=row.VerifiedBy
    )

    # 2. Fetch Private Data if Token is valid
    if token:
        # Here you would typically verify the token with Microsoft
        # Fetch Extended Data
        cursor.execute("SELECT CompleteReport, InternalNotes, LastMaintenance, WarrantyLeft FROM PanelDetails WHERE PanelId = ?", id)
        ext_row = cursor.fetchone()
        if ext_row:
            response.additionalData = {
                "completeReport": ext_row.CompleteReport,
                "notes": ext_row.InternalNotes,
                "lastMaintenanceDate": str(ext_row.LastMaintenance),
                "warrantyLeft": ext_row.WarrantyLeft
            }
        
        # Fetch Components
        cursor.execute("SELECT SectionName, ComponentName, Make, SerialNumber, Warranty FROM Components WHERE PanelId = ?", id)
        components = []
        for c_row in cursor.fetchall():
            components.append(Component(
                sectionName=c_row.SectionName,
                componentName=c_row.ComponentName,
                make=c_row.Make,
                serialNumber=c_row.SerialNumber,
                warranty=c_row.Warranty
            ))
        response.components = components

    conn.close()
    return response

@app.post("/raise_ticket")
def raise_ticket(ticket: dict):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO Tickets (PanelId, Description, ContactInfo, Status) VALUES (?, ?, ?, 'Open')",
            (ticket['panelId'], ticket['description'], ticket['contactInfo'])
        )
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
