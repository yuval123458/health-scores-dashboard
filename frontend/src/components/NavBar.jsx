import React from "react";
import { Link } from "react-router-dom";

const NavBar = () => {
  return (
    <nav className="bg-gray-800 text-white px-3 py-4 flex mb-6 justify-between">
      <h1 className="font-bold text-lg">Botson.ai</h1>
      <div className="space-x-4">
        <Link to="/dashboard" className="hover:underline">
          Dashboard
        </Link>
        <Link to="/assistant" className="hover:underline">
          Assistant
        </Link>
      </div>
    </nav>
  );
};

export default NavBar;
