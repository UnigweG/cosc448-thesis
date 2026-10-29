// let auth = require("../app/middleware/auth");
// let chai = require("chai");
// let chaiHttp = require("chai-http");
// let server = require("../server");
// chai.use(chaiHttp);
// let expect = chai.expect;
// let should = chai.should();
// let token = auth.setToken("consumer", "1");

// //mocha test stripe invoice end points
// describe("POST /api/stripe/invoice", () => {
//   it("stripe invoice create", (done) => {
//     chai
//       .request(server)
//       .post("/api/stripe/invoice")
//       .set("Authorization", `Bearer ${token}`)
//       .send({
//         customer: "cus_MBnCdYT4aL4tfU",
//         subscription: "sub_EqXqXqXqXqXqXqXq",
//         amount: 1000,
//         currency: "usd",
//         description: "test invoice",
//         metadata: {
//           test: "test",
//         },
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

// describe("GET /api/stripe/invoice", () => {
//   it("stripe invoice findAll", (done) => {
//     chai
//       .request(server)
//       .get("/api/stripe/invoice")
//       .set("Authorization", `Bearer ${token}`)
//       .end((error, res) => {
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

// describe("GET /api/stripe/invoice", () => {
//   it("stripe invoice findAll with send", (done) => {
//     chai
//       .request(server)
//       .get("/api/stripe/invoice/")
//       .set("Authorization", `Bearer ${token}`)
//       .send({
//         name: "bobby",
//         address: "1234 bobby street",
//       })
//       .end((error, res) => {
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

// describe("GET /api/stripe/invoice", () => {
//   it("stripe invoice findOne", (done) => {
//     chai
//       .request(server)
//       .get("/api/stripe/invoice/in_1LSeKfJ1ttqNM1k3Ed6BrTvk")
//       .set("Authorization", `Bearer ${token}`)
//       .send()
//       .end((error, res) => {
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

// describe("PUT /api/stripe/invoice", () => {
//   it("stripe invoice update", (done) => {
//     chai
//       .request(server)
//       .put("/api/stripe/invoice/in_1LSeKfJ1ttqNM1k3Ed6BrTvk")
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

// describe("DELETE /api/stripe/invoice", () => {
//   it("stripe invoice delete", (done) => {
//     chai
//       .request(server)
//       .delete("/api/stripe/invoice/in_1LSeKfJ1ttqNM1k3Ed6BrTvk")
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
