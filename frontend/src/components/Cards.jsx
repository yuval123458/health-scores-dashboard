import React from "react";
import StatCard from "./StatCard";
import {
  FaDatabase,
  FaMapMarkerAlt,
  FaCheckCircle,
  FaUsers,
  FaChartLine,
  FaPercentage,
} from "react-icons/fa";
import { MdSmsFailed, MdWarning } from "react-icons/md";
import { GiReceiveMoney } from "react-icons/gi";

const Cards = ({ summary }) => {
  return (
    <>
      <StatCard
        title="Total Records"
        value={summary.totalRecords}
        icon={<FaDatabase />}
      />
      <StatCard
        title="No Coordinates"
        value={summary.totalNoCoords}
        icon={<FaMapMarkerAlt />}
      />
      <StatCard
        title="Completed Feeds"
        value={summary.totalDeals}
        icon={<FaCheckCircle />}
      />
      <StatCard
        title="Unique Sources"
        value={summary.uniqueSources}
        icon={<FaUsers />}
      />
      <StatCard
        title="Failed Indexing"
        value={summary.totalFailed}
        icon={<MdSmsFailed />}
      />
      <StatCard
        title="Failed Enrichment"
        value={summary.totalNoMetadata}
        icon={<MdWarning />}
      />
      <StatCard
        title="Avg. Jobs per Feed"
        value={summary.avgJobsPerFeed?.toFixed(0)}
        icon={<FaChartLine />}
      />
      <StatCard
        title="Indexing Success Rate"
        value={`${summary.indexingSuccessRate?.toFixed(1)}%`}
        icon={<FaPercentage />}
      />
      <StatCard
        title="Metadata Coverage Rate"
        value={`${summary.metadataCoverageRate?.toFixed(1)}%`}
        icon={<GiReceiveMoney />}
      />
    </>
  );
};

export default Cards;
