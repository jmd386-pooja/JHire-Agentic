const { PrismaClient } = require('@prisma/client');
const bcrypt = require('bcryptjs');

const prisma = new PrismaClient();

async function main() {
  // Static user details
  const staticUsers = [
    {
      email: 'jeffrin@gmail.com',
      name: 'Jeffrin',
      password: '1234567890', // plain text password
      role: 'USER',
    },
    {
      email: 'sabareeshwaran.m@jmangroup.com',
      name: 'Sabareeshwaran',
      password: '1234567890', // plain text password
      role: 'USER',
    },
  ];

  for (const user of staticUsers) {
    // Check if the user already exists
    const existingUser = await prisma.user.findUnique({
      where: { email: user.email },
    });

    if (!existingUser) {
      // Hash the password before saving
      const hashedPassword = await bcrypt.hash(user.password, 12);

      await prisma.user.create({
        data: {
          email: user.email,
          name: user.name,
          password: hashedPassword,
          role: user.role,
        },
      });

      console.log(`User ${user.email} created successfully.`);
    } else {
      console.log(`User ${user.email} already exists. Skipping creation.`);
    }
  }
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
