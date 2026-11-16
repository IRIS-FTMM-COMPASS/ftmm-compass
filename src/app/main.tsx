import React from "react"
import ReactDOM from "react-dom/client"
import App from "@/app/App"
import ErrorBoundary from "@/app/components/ErrorBoundary"
import "@/index.css"

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary fallbackTitle="Terjadi Kendala pada Aplikasi FTMM Compass">
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
)
