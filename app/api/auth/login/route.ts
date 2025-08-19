import { NextResponse } from "next/server";
import prisma from "@/lib/prisma";
import { compare } from "bcryptjs";
import { sign } from "jsonwebtoken";

export async function POST(req: Request) {
  try {
    const { email, password, uniqueId } = await req.json();

    if(!uniqueId){// Check in User table
    const user = await prisma.user.findUnique({ where: { email } });

    if (user) {
      const isPasswordValid = await compare(password, user.password);

      if (!isPasswordValid) {
        return NextResponse.json(
          { error: "Invalid credentials" },
          { status: 401 }
        );
      }

      const token = sign(
        { userId: user.id, email: user.email, role: "user" },
        process.env.JWT_SECRET!,
        { expiresIn: "1d" }
      );

      const response = NextResponse.json(
        { message: "Login successful", redirect: "/candidates" },
        { status: 200 }
      );

      response.cookies.set("user_token", token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "strict",
        maxAge: 86400, // 1 day
      });
    

      return response;
    }
  }

    // Check in Candidate
    const candidate = await prisma.candidate.findFirst({
      where: {
        temp_name: uniqueId,
        tempPassword: password,
        email,
      },
    });
    if (uniqueId){
    if (candidate) {
      const token = sign(
        {
          candidateId: candidate.id,
          temp_name: candidate.temp_name,
          role: "candidate",
        },
        process.env.JWT_SECRET!,
        { expiresIn: "1d" }
      );

      const candidateid = candidate.id
      const candidateName = candidate.name
      const voice = candidate.Voice
      const avatar = candidate.Avatar
      const skills = candidate.Skills

      const response = NextResponse.json(
        { message: "Login successful", redirect: "/Instructions" },
        { status: 200 }
      );
      response.cookies.set("candidate_token", token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "strict",
        maxAge: 86400, // 1 day
      });
      
      response.cookies.set("candidate_name", candidateName, {
        secure: process.env.NODE_ENV === "production",
        sameSite: "strict",
        maxAge: 86400,
      });

      response.cookies.set("candidate_id", candidateid.toString(), {
        secure: process.env.NODE_ENV === "production",
        sameSite: "strict",
        maxAge: 86400,
      });

      response.cookies.set("token", token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "strict",
        maxAge: 86400,       
      });

      response.cookies.set("avatar", avatar?avatar : "None", {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "strict",
        maxAge: 86400,
      });

      response.cookies.set("voice", voice?voice : "None", {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "strict",
        maxAge: 86400,
      });

      response.cookies.set("skills", skills.toString(), {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "strict",
        maxAge: 86400,
      });

      return response;
    }
  }

    return NextResponse.json(
      { error: "Invalid credentials" },
      { status: 401 }
    );
  } catch (error) {
    console.error(error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}




// import { NextResponse } from "next/server";
// import prisma from "@/lib/prisma";
// import { compare } from "bcryptjs";
// import { sign } from "jsonwebtoken";

// export async function POST(req: Request) {
//   try {
//     const { email, password, uniqueId } = await req.json();

//     if (!uniqueId) {
//       // User Login
//       const user = await prisma.user.findUnique({ where: { email } });

//       if (user) {
//         const isPasswordValid = await compare(password, user.password);

//         if (!isPasswordValid) {
//           return NextResponse.json(
//             { error: "Invalid credentials" },
//             { status: 401 }
//           );
//         }

//         const token = sign(
//           { userId: user.id, email: user.email, role: "user" },
//           process.env.JWT_SECRET!,
//           { expiresIn: "1d" }
//         );

//         const response = NextResponse.json(
//           { message: "Login successful", redirect: "/candidates" },
//           { status: 200 }
//         );

//         response.cookies.set("user_token", token, {
//           httpOnly: true,
//           secure: process.env.NODE_ENV === "production",
//           sameSite: "strict",
//           maxAge: 86400, // 1 day
//         });

//         return response;
//       }
//     } else {
//       // Candidate Login
//       const candidate = await prisma.candidate.findFirst({
//         where: {
//           temp_name: uniqueId,
//           tempPassword: password,
//           email,
//         },
//       });

//       if (candidate) {
//         const token = sign(
//           {
//             candidateId: candidate.id,
//             temp_name: candidate.temp_name,
//             role: "candidate",
//           },
//           process.env.JWT_SECRET!,
//           { expiresIn: "1d" }
//         );
        

//         const response = NextResponse.json(
//           { message: "Login successful", redirect: "/Instructions" },
//           { status: 200 }
//         );

//         response.cookies.set("candidate_token", token, {
//           httpOnly: true,
//           secure: process.env.NODE_ENV === "production",
//           sameSite: "strict",
//           maxAge: 86400, // 1 day
//         });

//         return response;
//       }
//     }

//     return NextResponse.json(
//       { error: "Invalid credentials" },
//       { status: 401 }
//     );
//   } catch (error) {
//     console.error(error);
//     return NextResponse.json(
//       { error: "Internal server error" },
//       { status: 500 }
//     );
//   }
// }
