import React from "react";
import RegressionChart from "./RegressionChart";
import BlockChart from "./BlockChart";

const Charts = ({ lineData, countryData }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
      <RegressionChart lineData={lineData} />
      <BlockChart countryData={countryData} />
    </div>
  );
};

export default Charts;
