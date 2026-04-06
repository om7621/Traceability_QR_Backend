import os
from fastapi import FastAPI, HTTPException, Depends, Header
from typing import Optional, List
import pyodbc
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Enable CORS for your Flutter Web App
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yellow-coast-0ea82d100.7.azurestaticapps.net", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuration ---
# Updated with your actual Azure SQL details
DB_CONNECTION_STRING = (
    "Driver={ODBC Driver 18 for SQL Server};"
    "Server=tcp:newen-server.database.windows.net,1433;"
    "Database=newen_traceability_db;"
    "Uid=omsingh;"
    "Pwd=Singhisblink7621;"
    "Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=30;"
)

# --- Models ---
class ComponentModel(BaseModel):
    sectionName: str
    componentName: str
    make: str
    serialNumber: str
    warranty: str = "Standard"

class PanelResponse(BaseModel):
    projectName: str
    panel_sr_no: str
    startDate: str
    verifiedBy: str
    companyName: str = "Newen Systems Pvt Ltd"
    status: str
    productType: strpreparedBy: Optional[str] = None
    remarks: Optional[str] = None
    components: Optional[List[ComponentModel]] = None
    referenceDocument: Optional[str] = None # Added this
# ... inside get_panel_details ...
        response = PanelResponse(
            projectName=row.project_name or "N/A",
            panel_sr_no=row.panel_serial,
            startDate=str(row.start_date) if row.start_date else "N/A",
            verifiedBy=row.verified_by or "N/A",
            status=row.status or "Unknown",
            productType=row.product_type or "N/A",
            referenceDocument=row.reference_document # Added this
        )


# --- Helper Functions ---
def get_db_connection():
    try:
        return pyodbc.connect(DB_CONNECTION_STRING)
    except Exception as e:
        print(f"DB Connection Error: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

# --- Endpoints ---

@app.get("/")
def read_root():
    return {"message": "Newen Traceability API is Online"}

@app.get("/get_panel_details", response_model=PanelResponse)
def get_panel_details(id: str, authenticated: bool = False):
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Fetch Panel Data from [dbo].[Panels]
    cursor.execute("""
        SELECT project_name, panel_serial, start_date, verified_by, product_type, prepared_by, remarks, status
        FROM Panels
        WHERE panel_serial = ?
    """, id)
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Panel not registered in system")

    response = PanelResponse(
        projectName=row.project_name or "N/A",
        panel_sr_no=row.panel_serial,
        startDate=str(row.start_date) if row.start_date else "N/A",
        verifiedBy=row.verified_by or "N/A",
        status=row.status or "Unknown",
        productType=row.product_type or "N/A"
    )

    # 2. Fetch Components Data if authenticated
    if authenticated:
        response.preparedBy = row.prepared_by
        response.remarks = row.remarks

        cursor.execute("""
            SELECT section_name, component_name, make, serial_number
            FROM Components
            WHERE panel_serial = ?
        """, id)

        components = []
        for c_row in cursor.fetchall():
            components.append(ComponentModel(
                sectionName=c_row.section_name,
                componentName=c_row.component_name,
                make=c_row.make,
                serialNumber=c_row.serial_number
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
            "INSERT INTO Tickets (panel_serial, description, contact_info, status) VALUES (?, ?, ?, 'Open')",
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
