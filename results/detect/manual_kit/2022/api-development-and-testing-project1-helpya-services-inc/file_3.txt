const sql = require("./db.js");
const stripe = require("stripe")(
  "sk_test_51LN9iJJ1ttqNM1k30e0LTKwvIU6ZPdeCyPewNhuYCpipuSGjvhyKwBJZDM4v24b1LANdAF17amgq6H9fJHIZIG8O00oR8i1Ari"
);

// constructor
const consumer = function (consumer) {
  this.fname_of_consumer = consumer.fname_of_consumer;
  this.lname_of_consumer = consumer.lname_of_consumer;
  this.email = consumer.email;
  this.phone_number = consumer.phone_number;
  this.location = consumer.location;
  this.consumer_profile = consumer.consumer_profile;
  this.password = consumer.password;
  this.role = consumer.role;
  this.active_account = consumer.active_account;
};

consumer.create = async (newconsumer, result) => {
  console.log(newconsumer);
  console.log(
    "dasjd;asjdsadlkajd;sajdsakd;laskdlsadj;lsajd;sakd;sajd;aksdlsa;lkdjlkasdj;laskdalsk"
  );
  const Stripecustomer = await stripe.customers.create({});
  sql.query(
    `INSERT INTO consumer (fname_of_consumer, lname_of_consumer, email, phone_number, location, consumer_profile, password, role, active_account, strip_customer_id) VALUES ('${newconsumer.fname_of_consumer}','${newconsumer.lname_of_consumer}','${newconsumer.email}','${newconsumer.phone_number}','${newconsumer.location}','${newconsumer.consumer_profile}','${newconsumer.password}','${newconsumer.role}','${newconsumer.active_account}','${Stripecustomer.id}');`,
    (err, res) => {
      if (err) {
        console.log("error: ", err);
        result(err, null);
        return;
      }
      console.log("created consumer: ", { id: res.insertId, ...newconsumer, ...Stripecustomer.id });
      result(null, { id: res.insertId, ...newconsumer });
    }
  );
};

consumer.findById = (id, result) => {
  sql.query(`SELECT * FROM consumer WHERE consumerID = ${id}`, (err, res) => {
    if (err) {
      console.log("error: ", err);
      result(err, null);
      return;
    }
    if (res.length) {
      console.log("found consumer: ", res[0]);
      result(null, res[0]);
      return;
    }
    // not found consumer with the id
    result({ kind: "not_found" }, null);
  });
};

consumer.getAll = (result, title) => {
  let query = "SELECT * FROM consumer";
  if (title) {
    query += ` WHERE title LIKE '%${title}%'`;
  }
  sql.query(query, (err, res) => {
    if (err) {
      console.log("error: ", err);
      result(null, err);
      return;
    }
    console.log("consumer: ", res);
    result(null, res);
  });
};

/*
consumer.getAllPublished = (result) => {
  sql.query("SELECT * FROM consumer WHERE published=true", (err, res) => {
    if (err) {
      console.log("error: ", err);
      result(null, err);
      return;
    }
    console.log("consumer: ", res);
    result(null, res);
  });
};
*/

consumer.updateById = (id, consumer, result) => {
  sql.query(
    "UPDATE consumer SET fname_of_consumer = ?, lname_of_consumer = ?, email = ?, phone_number = ?, location = ?, consumer_profile = ? WHERE consumerID = ?",
    [
      consumer.fname_of_consumer,
      consumer.lname_of_consumer,
      consumer.email,
      consumer.phone_number,
      consumer.location,
      consumer.consumer_profile,
      id,
    ],
    (err, res) => {
      if (err) {
        console.log("error: ", err);
        result(null, err);
        return;
      }
      if (res.affectedRows == 0) {
        // not found consumer with the id
        result({ kind: "not_found" }, null);
        return;
      }
      console.log("updated consumer: ", { id: id, ...consumer });
      result(null, { id: id, ...consumer });
    }
  );
};
consumer.remove = (id, result) => {
  sql.query("DELETE FROM consumer WHERE consumerID = ?", id, (err, res) => {
    if (err) {
      console.log("error: ", err);
      result(null, err);
      return;
    }
    if (res.affectedRows == 0) {
      // not found consumer with the id
      result({ kind: "not_found" }, null);
      return;
    }
    console.log("deleted consumer with id: ", id);
    result(null, res);
  });
};
consumer.removeAll = (result) => {
  sql.query("DELETE FROM consumer", (err, res) => {
    if (err) {
      console.log("error: ", err);
      result(null, err);
      return;
    }
    console.log(`deleted ${res.affectedRows} consumer`);
    result(null, res);
  });
};
module.exports = consumer;
