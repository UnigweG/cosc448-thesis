// let auth = require("../app/middleware/auth");
// let chai = require("chai");
// let chaiHttp = require("chai-http");
// let server = require("../server");
// chai.use(chaiHttp);
// let expect = chai.expect;
// let should = chai.should();
// let token = auth.setToken("consumer", "1");

// //mocha test stripe customer end points
// describe("POST /api/stripe/customer", () => {
//   it("stripe customer create", (done) => {
//     chai
//       .request(server)
//       .post("/api/stripe/customer")
//       .set("Authorization", `Bearer ${token}`)
//       .send({
//         name: "bob",
//         email: "bob@bob.com",
//         phone: "1234567890",
//         address: "1234 bob street",
//         city: "bob city",
//         state: "bob state",
//         zip: "12345",
//         country: "bob country",
//       })
//       .end((err, res) => {
//         if (res) {
//           res.should.have.status(200);
//           res.body.should.be.a("object");
//           console.log(res.body);
//         } else {
//           console.log("result is null");
//         }
//       });
//     done();
//   });
// });

// describe("GET /api/stripe/customer", () => {
//   it("stripe customer findAll", (done) => {
//     chai
//       .request(server)
//       .get("/api/stripe/customer")
//       .set("Authorization", `Bearer ${token}`)
//       .end((error, response) => {
//         if (res) {
//           res.should.have.status(200);
//           res.body.should.be.a("object");
//           console.log(res.body);
//         } else {
//           console.log("result is null");
//         }
//       });
//     done();
//   });
// });

// describe("GET /api/stripe/customer", () => {
//   it("stripe customer findAll with send", (done) => {
//     chai
//       .request(server)
//       .get("/api/stripe/customer/")
//       .set("Authorization", `Bearer ${token}`)
//       .send({
//         name: "bobby",
//         address: "1234 bobby street",
//       })
//       .end((error, response) => {
//         if (res) {
//           res.should.have.status(200);
//           res.body.should.be.a("object");
//           console.log(res.body);
//         } else {
//           console.log("result is null");
//         }
//       });
//     done();
//   });
// });

// describe("GET /api/stripe/customer", () => {
//   it("stripe customer findOne", (done) => {
//     chai
//       .request(server)
//       .get("/api/stripe/customer/:id")
//       .set("Authorization", `Bearer ${token}`)
//       .end((error, response) => {
//         if (res) {
//           res.should.have.status(200);
//           res.body.should.be.a("object");
//           console.log(res.body);
//         } else {
//           console.log("result is null");
//         }
//       });
//     done();
//   });
// });

// describe("PUT /api/stripe/customer", () => {
//   it("stripe customer update", (done) => {
//     chai
//       .request(server)
//       .put("/api/stripe/customer/:id")
//       .set("Authorization", `Bearer ${token}`)
//       .send({
//         name: "bob",
//         email: "bob@bob.com",
//         password: "password",
//         phone: "1234567890",
//         address: "1234 bob street",
//         city: "bob city",
//         state: "bob state",
//         zip: "12345",
//         country: "bob country",
//       })
//       .end((err, res) => {
//         if (res) {
//           res.should.have.status(200);
//           res.body.should.be.a("object");
//           console.log(res.body);
//         } else {
//           console.log("result is null");
//         }
//       });
//     done();
//   });
// });

// describe("DELETE /api/stripe/customer", () => {
//   it("stripe customer delete", (done) => {
//     chai
//       .request(server)
//       .delete("/api/stripe/customer/:id")
//       .set("Authorization", `Bearer ${token}`)
//       .end((err, res) => {
//         if (res) {
//           res.should.have.status(200);
//           res.body.should.be.a("object");
//           console.log(res.body);
//         } else {
//           console.log("result is null");
//         }
//       });
//     done();
//   });
// });
