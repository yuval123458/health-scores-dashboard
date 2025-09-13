import { useState } from "react";
import NavBar from "./components/NavBar";
import Dashboard from "./components/Dashboard";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

function App() {
  return (
    <Dashboard />
  );
}

export default App;
