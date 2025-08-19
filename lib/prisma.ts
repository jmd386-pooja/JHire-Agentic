import { PrismaClient} from "@prisma/client";

const PrismaClientSinglton=()=>{
    return new PrismaClient()
}

const globalForPrisma=global as unknown as {prisma: PrismaClient | undefined};

const prisma = globalForPrisma.prisma?? PrismaClientSinglton();

export default prisma;