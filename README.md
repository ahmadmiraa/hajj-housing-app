# hajj-housing-app
An open-source automation tool for Hajj pilgrim housing and hotel room assignment. Built with Python and Streamlit, it automates the sorting process based on family ties and room capacity, featuring an interactive analytics dashboard. 🕋📊

# 🕋 Hajj Housing Automation System

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

An interactive web application built with **Python** and **Streamlit** designed to automate the complex logistical task of assigning hotel rooms for Hajj and Umrah pilgrims. The system processes raw pilgrim lists to generate optimized rooming schedules while strictly adhering to gender separation rules and maintaining family proximity.

## ✨ Key Features

* **⚡ Full Automation:** Converts unstructured or semi-structured Excel lists into a finalized rooming manifest in seconds.
* **👨‍👩‍👧‍👦 Family-Centric Logic:** Utilizes a smart heuristic algorithm to keep family members (identified by a unique Family ID) in sequential rooms, ensuring proximity even when genders are separated.
* **📊 Interactive Dashboard:** Real-time analytics and visualization of room occupancy rates, gender distribution, and room type requirements.
* **📥 Smart Templates:** Provides users with a downloadable Excel template to ensure data integrity and minimize input errors.
* **🔒 Privacy Focused:** All data processing happens in temporary sessions; no personal data is permanently stored on the server.

## 🚀 Live Demo

Try the application live here:
[Insert your Streamlit App URL here]

---

## 🛠️ Usage Guide

To ensure optimal results, please follow these guidelines when preparing your Excel file:

### 1. Data Preparation
Your Excel file must contain the following columns (order does not matter):

| Family ID | Room Type | Gender | Full Name |
| :--- | :--- | :--- | :--- |
| Unique ID for the family | 2, 3, 4, 5, or Shared | Male / Female | Pilgrim's Name |

> **Pro Tip:** The `Family ID` is the most critical column. To ensure a husband and wife are placed in rooms near each other (e.g., across the hall), assign them the exact same ID (e.g., 101).

### 2. Running the Tool
1. Open the application link.
2. Upload your prepared Excel file.
3. Wait for the automated processing.
4. Download the final housing manifest (Excel format) and view the analytics.

---

## 💻 Local Development

If you wish to run this project locally or contribute to the code:

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/your-username/hajj-housing-app.git](https://github.com/your-username/hajj-housing-app.git)
   cd hajj-housing-app

```

2. **Install dependencies:**
```bash
pip install -r requirements.txt

```


3. **Run the app:**
```bash
streamlit run app.py

```



## 🧰 Tech Stack

* **[Streamlit](https://streamlit.io/):** For the interactive frontend and web interface.
* **[Pandas](https://pandas.pydata.org/):** For data manipulation and algorithmic sorting.
* **[Plotly](https://plotly.com/):** For generating dynamic charts and visualizations.
* **[OpenPyXL/XlsxWriter](https://openpyxl.readthedocs.io/):** For Excel file I/O operations.

## 🤝 Contribution

Contributions are welcome! If you have suggestions for optimizing the sorting algorithm or adding new features, please feel free to open an Issue or submit a Pull Request.

---

Developed by Ahmad Mira

