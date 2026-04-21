# LandChain: Decentralized Land Registration System

**LandChain** is a secure, transparent, and immutable land registration portal designed to eliminate property fraud. By leveraging blockchain principles, the system ensures that land records are tamper-proof and ownership history is easily verifiable.

## 🚀 Project Overview
In traditional systems, land records are prone to manual errors and unauthorized alterations. **LandChain** solves this by providing a decentralized ledger where every land deed is cryptographically hashed and stored securely.

## ✨ Key Features
* **Blockchain-Based Ledger**: Secure and immutable record-keeping of land ownership.
* **Digital Deed Generation**: Automated generation of land deeds stored in the `/deeds` module.
* **User Authentication**: Secure login system with encrypted credential management.
* **Property Search & Verification**: Publicly verifiable land records to prevent duplicate sales.
* **Database Integration**: Reliable storage of transactional data using SQLite.

## 🏗️ Project Structure
The project is organized into professional modules for better scalability:

* **/frontend**: The core application logic (`app.py`), blockchain engine (`blockchain.py`), and UI components (`templates` & `static`).
* **/modules**: Configuration files and user management data.
* **/deeds**: A repository for all generated property documents and certificates.
* **registry.db**: The local database for persistent record storage.

## 🛠️ Technology Stack
* **Language**: Python (Flask/Streamlit)
* **Blockchain Logic**: Custom Decentralized Ledger Protocol
* **Database**: SQLite3
* **Frontend**: HTML5, CSS3, JavaScript
* **Security**: SHA-256 Hashing for block integrity

## ⚙️ Installation & Setup
1. **Clone the Repository**:
   ```bash
   git clone [https://github.com/marymicy/LandChain-Blockchain-Land-Registry.git](https://github.com/marymicy/LandChain-Blockchain-Land-Registry.git)
