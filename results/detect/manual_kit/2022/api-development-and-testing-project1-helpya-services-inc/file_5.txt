const sql = require("./db.js");
// constructor
const ad = function (ad) {
  this.adID = ad.adID;
  this.businessID = ad.businessID;
  this.ad_title = ad.job_title;
  this.ad_body = ad.ad_body;
  this.location = ad.location;
  this.rate_per_hour = ad.rate_per_hourl;
};
ad.create = (newad, result) => {
  sql.query("INSERT INTO ads SET ?", newad, (err, res) => {
    if (err) {
      console.log("error: ", err);
      result(err, null);
      return;
    }
    result(null, "success");
  });
};

ad.createPayment_History = (paymentHistory, result) => {
  sql.query(
    "INSERT INTO ads SET payment_history VALUES ?",
    paymentHistory,
    (err, res) => {
      if (err) {
        console.log("error: ", err);
        result(err, null);
        return;
      }
      result(null, { id: res.insertId, ...newad });
    }
  );
};
//find specific ad
ad.findById = (id, result) => {
  sql.query(`SELECT * FROM ads WHERE adID = ${id}`, (err, res) => {
    if (err) {
      console.log("error: ", err);
      result(err, null);
      return;
    }
    if (res.length) {
      console.log("found ad: ", res);
      result(null, res);
      return;
    }
    // not found ad with the id
    result({ kind: "not_found" }, null);
  });
};
ad.getAll = (result) => {
  let query = "SELECT * FROM ads";

  sql.query(query, (err, res) => {
    if (err) {
      console.log("error: ", err);
      result(null, err);
      return;
    }
    result(null, res);
  });
};
//get all business's ads
ad.getAllAds = (name_of_business, result) => {
  sql.query(
    `SELECT * FROM ads WHERE business_name = ${name_of_business}`,
    (err, res) => {
      if (err) {
        console.log("error: ", error);
        result(null, err);
        return;
      }
      console.log(`found ads for business: ${name_of_business}`, res);
      result(null, res);
    }
  );
};
//update a specific ad
ad.updateById = (id, ad, result) => {
  sql.query(
    "UPDATE ads SET business_name = ?, job_title = ?, job_category = ?, location = ?, rate_per_hour = ? WHERE adID = ?",
    [ad.ad_title, ad.job_body, ad.location, ad.rate_per_hour, id],
    (err, res) => {
      if (err) {
        console.log("error: ", err);
        result(null, err);
        return;
      }
      if (res.affectedRows == 0) {
        // not found ad with the id
        result({ kind: "not_found" }, null);
        return;
      }
      result(null, "success");
    }
  );
};
//removes a specific ad from business
ad.remove = (id, result) => {
  sql.query("DELETE FROM ads WHERE adID = ?", id, (err, res) => {
    if (err) {
      console.log("error: ", err);
      result(null, err);
      return;
    }
    if (res.affectedRows == 0) {
      // not found ad with the id
      result({ kind: "not_found" }, null);
      return;
    }
    result(null, "success");
  });
};
//removes all ads for a business
ad.removeAll = (result) => {
  sql.query("DELETE FROM ads WHERE businessID = ?", (err, res) => {
    if (err) {
      console.log("error: ", err);
      result(null, err);
      return;
    }
    result(null, res);
  });
};
module.exports = ad;
