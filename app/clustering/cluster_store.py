import logging
from collections import Counter

logger = logging.getLogger(__name__)


class ClusterStore:
    """Persist and query cluster results in the database."""

    @staticmethod
    def save_results(db, step_ids, labels, cluster_labels, threshold):
        """Save clustering results to database.

        Args:
            db: sqlite3 connection
            step_ids: list of step IDs
            labels: numpy array of cluster assignments (-1 = noise)
            cluster_labels: dict of cluster_id -> label text
            threshold: similarity threshold used
        """
        db.execute("DELETE FROM cluster_results")
        db.execute("DELETE FROM cluster_info")

        for i, step_id in enumerate(step_ids):
            cid = int(labels[i])
            clabel = cluster_labels.get(cid, "")
            db.execute(
                "INSERT INTO cluster_results (step_id, cluster_id, cluster_label, similarity_threshold) "
                "VALUES (?, ?, ?, ?)",
                (int(step_id), cid, clabel, threshold)
            )

        # Compute and save cluster info
        unique_labels = set(int(l) for l in labels)
        unique_labels.discard(-1)
        label_counts = Counter(int(l) for l in labels)

        for cid in unique_labels:
            step_count = label_counts[cid]
            case_ids = db.execute(
                "SELECT DISTINCT ts.case_id FROM cluster_results cr "
                "JOIN test_steps ts ON cr.step_id = ts.id "
                "WHERE cr.cluster_id = ?",
                (cid,)
            ).fetchall()
            case_count = len(case_ids)

            db.execute(
                "INSERT INTO cluster_info (cluster_id, label, step_count, case_count, threshold) "
                "VALUES (?, ?, ?, ?, ?)",
                (cid, cluster_labels.get(cid, ""), step_count, case_count, threshold)
            )

        db.commit()
        logger.info("Saved cluster results: %d clusters", len(unique_labels))

    @staticmethod
    def get_cluster_list(db):
        """Return all clusters for list view."""
        rows = db.execute(
            "SELECT cluster_id, label, step_count, case_count "
            "FROM cluster_info ORDER BY cluster_id"
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_cluster_detail(db, cluster_id):
        """Return all steps in a cluster with their case info."""
        rows = db.execute(
            "SELECT ts.id as step_id, ts.operation, ts.step_no, ts.case_id, tc.title as case_title "
            "FROM cluster_results cr "
            "JOIN test_steps ts ON cr.step_id = ts.id "
            "JOIN test_cases tc ON ts.case_id = tc.id "
            "WHERE cr.cluster_id = ? "
            "ORDER BY ts.case_id, ts.step_no",
            (cluster_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_sibling_steps(db, step_id, limit=10):
        """Return other steps in the same cluster as the given step."""
        cluster_row = db.execute(
            "SELECT cluster_id FROM cluster_results WHERE step_id = ?",
            (step_id,)
        ).fetchone()

        if not cluster_row or cluster_row['cluster_id'] < 0:
            return []

        rows = db.execute(
            "SELECT ts.case_id, tc.title as case_title, ts.step_no, ts.operation "
            "FROM cluster_results cr "
            "JOIN test_steps ts ON cr.step_id = ts.id "
            "JOIN test_cases tc ON ts.case_id = tc.id "
            "WHERE cr.cluster_id = ? AND cr.step_id != ? "
            "LIMIT ?",
            (cluster_row['cluster_id'], step_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]
