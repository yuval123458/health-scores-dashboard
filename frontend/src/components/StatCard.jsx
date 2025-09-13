import React from "react";

const StatCard = ({ title, value, icon }) => {
  return (
    <div className="bg-white dark:bg-gray-800 shadow rounded-xl p-4 flex items-center justify-between">
      <div>
        <p className="text-sm text-gray-500 dark:text-gray-300">{title}</p>
        <p className="text-2xl font-semibold text-gray-900 dark:text-white">
          {value}
        </p>
      </div>
      {icon && <div className="text-3xl text-blue-500">{icon}</div>}
    </div>
  );
};

export default StatCard;
